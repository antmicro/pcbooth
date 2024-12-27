"""World, scene and render engine setup and rendering handler functions module."""

import bpy
import logging
from pathlib import Path
from typing import Callable, Tuple, Optional

from bpy.types import Image
from pcbooth.modules.file_io import stdout_redirected, execute_cmd
import pcbooth.modules.config as config
from typing import Dict, List, Callable
from pcbooth.modules.file_io import remove_file, mkdir
from glob import glob

from re import match
from os import listdir

logger = logging.getLogger(__name__)

CACHE_FORMAT = "PNG"
CACHE_NAME = "_tmp_render"


def setup_ultralow_cycles() -> Tuple[bpy.types.PropertyGroup, bpy.types.PropertyGroup]:
    """
    Configure the Cycles render engine for ultra-low quality and to minimize the time required to render an image.
    """
    cycles = bpy.context.scene.cycles
    cycles.samples = 1
    cycles.use_denoising = False
    cycles.max_bounces = 0
    cycles.caustics_reflective = False
    cycles.caustics_refractive = False
    cycles.use_adaptive_sampling = False

    cycles_visibility = bpy.context.scene.world.cycles_visibility
    cycles_visibility.camera = False
    cycles_visibility.diffuse = False
    cycles_visibility.glossy = False
    cycles_visibility.transmission = False
    cycles_visibility.scatter = False

    bpy.context.scene.render.film_transparent = False


def restore_default_cycles() -> None:
    """
    Restore Cycles and Cycles visibility settings to default, then initialize renderer from config.
    This will restore GPU and compositing settings as well.
    """
    cycles = bpy.context.scene.cycles
    for prop in dir(cycles):
        if not prop.startswith("_") and hasattr(cycles, prop):
            try:
                default_value = bpy.types.CyclesSettings.bl_rna.properties[prop].default
                setattr(cycles, prop, default_value)
            except AttributeError:
                pass

    cycles_visibility = bpy.context.scene.world.cycles_visibility
    for prop in dir(cycles_visibility):
        if not prop.startswith("_") and hasattr(cycles_visibility, prop):
            try:
                default_value = bpy.types.CyclesVisibilitySettings.bl_rna.properties[
                    prop
                ].default
                setattr(cycles_visibility, prop, default_value)
            except AttributeError:
                pass
    init_render_settings()


def compositing(set) -> Callable:
    """Compositing decorator, makes sure scene uses nodes and clears the current setup before changing it to another"""

    def _set_compositing() -> None:
        bpy.context.scene.use_nodes = True
        tree = bpy.context.scene.node_tree
        for node in tree.nodes:
            tree.nodes.remove(node)

        set()

    return _set_compositing


@compositing
def set_default_compositing() -> None:
    """Set default render compositing - applies glare effect for bloom."""
    tree = bpy.context.scene.node_tree

    rend_layers_node = tree.nodes.new(type="CompositorNodeRLayers")
    glare_node = tree.nodes.new(type="CompositorNodeGlare")
    glare_node.glare_type = "FOG_GLOW"
    glare_node.size = 5
    viewer_node = tree.nodes.new("CompositorNodeViewer")
    comp_node = tree.nodes.new("CompositorNodeComposite")

    links = tree.links
    links.new(rend_layers_node.outputs[0], glare_node.inputs[0])
    links.new(glare_node.outputs[0], viewer_node.inputs[0])
    links.new(glare_node.outputs[0], comp_node.inputs[0])


@compositing
def set_lqbw_compositing() -> None:
    """Set low-quality, black&white compositing for fast rendering of monochrome shapes"""
    tree = bpy.context.scene.node_tree

    rend_layers_node = tree.nodes.new(type="CompositorNodeRLayers")
    comp_node = tree.nodes.new("CompositorNodeComposite")
    mix_node = tree.nodes.new(type="CompositorNodeMixRGB")
    rgb_white_node = tree.nodes.new(type="CompositorNodeRGB")
    rgb_black_node = tree.nodes.new(type="CompositorNodeRGB")
    rgb_white_node.outputs[0].default_value[:] = 1, 1, 1, 1
    rgb_black_node.outputs[0].default_value[:] = 0.0, 0.0, 0.0, 1

    links = tree.links
    links.new(
        rend_layers_node.outputs["Alpha"],
        mix_node.inputs[0],
    )
    links.new(
        rgb_black_node.outputs["RGBA"],
        mix_node.inputs[1],
    )
    links.new(
        rgb_white_node.outputs["RGBA"],
        mix_node.inputs[2],
    )
    links.new(
        mix_node.outputs["Image"],
        comp_node.inputs["Image"],
    )


def setup_gpu() -> None:
    """
    Find compatible GPU devices and enable them for rendering.
    If no suitable GPU is found, use CPU instead.
    """
    cycles_preferences = bpy.context.preferences.addons["cycles"].preferences
    cycles_preferences.refresh_devices()
    logger.debug(
        f"Available devices: {[device for device in cycles_preferences.devices]}"
    )
    gpu_types = [
        "CUDA",
        "OPTIX",
        "HIP",
        "ONEAPI",
        "METAL",
    ]

    try:
        device = next(
            (dev for dev in cycles_preferences.devices if dev.type in gpu_types)
        )
        bpy.context.scene.cycles.device = "GPU"
        cycles_preferences.compute_device_type = device.type
        logger.info(f"Enabled GPU rendering with: {device.name}.")
    except StopIteration:
        device = next(
            (dev for dev in cycles_preferences.devices if dev.type == "CPU"), None
        )
        bpy.context.scene.cycles.device = "CPU"
        cycles_preferences.compute_device_type = "NONE"
        logger.info(f"No GPU device found, enabled CPU rendering with: {device.name}")
    device.use = True


def init_render_settings():
    """Setup initial renderer properties."""
    logger.info("Setting up initial render properties...")
    scene = bpy.context.scene
    renderer = bpy.context.scene.render

    renderer.resolution_x = int(config.blendcfg["SETTINGS"]["IMAGE_WIDTH"])
    renderer.resolution_y = int(config.blendcfg["SETTINGS"]["IMAGE_HEIGHT"])

    renderer.engine = "CYCLES"
    renderer.film_transparent = True
    renderer.use_file_extension = True
    renderer.use_persistent_data = True  # more memory used, faster renders

    scene.frame_start = 1
    scene.frame_end = int(config.blendcfg["SETTINGS"]["FPS"])
    scene.cycles.samples = config.blendcfg["SETTINGS"]["SAMPLES"]
    scene.cycles.use_denoising = True

    setup_gpu()


class RendererWrapper:
    """Class responsible for rendering images and frames within Blender."""

    def __init__(self) -> None:
        self.formats = config.blendcfg["SETTINGS"]["IMAGE_FORMAT"]
        self.img_ext = None
        self.cache = None
        self.cache_path = None
        self.tmb_x = config.blendcfg["SETTINGS"]["THUMBNAIL_WIDTH"]
        self.tmb_y = config.blendcfg["SETTINGS"]["THUMBNAIL_HEIGHT"]
        self.render_path = config.renders_path

    def _set_image_format(self, format: str) -> None:
        """
        Set render file format and assign matching color mode. Color mode defaults to RGBA,
        if the chosen format doesn't support transparency, fallbacks to RGB. Assigns
        image file extension
        """
        bpy.context.scene.render.image_settings.file_format = format
        self.img_ext = bpy.context.scene.render.file_extension
        try:
            bpy.context.scene.render.image_settings.color_mode = "RGBA"
        except TypeError:
            bpy.context.scene.render.image_settings.color_mode = "RGB"

    def _init_render(self, camera: bpy.types.Object) -> None:
        """
        Render initial image and save in  renders directory to be used as cache.
        Uses CACHE_FORMAT and CACHE_NAME variables to determine file name and extension.
        """
        scene = bpy.context.scene
        scene.camera = camera
        scene.render.filepath = self.render_path + CACHE_NAME

        self._set_image_format(CACHE_FORMAT)
        self.cache_path = scene.render.filepath + self.img_ext

        with stdout_redirected():
            bpy.ops.render.render(write_still=True)
        try:
            self.cache = bpy.data.images.load(self.cache_path)
            logger.debug(f"Render completed, saved temp file to: {self.cache_path}")
        except (RuntimeError, AttributeError):
            logger.error(f"Can't load cache from {self.cache_path}")

    @staticmethod
    def _save_render(image: bpy.types.Image, filepath: str) -> None:
        try:
            image.save_render(filepath=filepath)
            logger.info(f"Saved render as: {bpy.path.relpath(filepath)}")
        except (RuntimeError, AttributeError):
            logger.error(f"Save failed for {bpy.path.relpath(filepath)}")

    def render(
        self,
        camera: bpy.types.Object,
        file_name: str,
        format_override: Optional[str] = None,
    ) -> bpy.types.Image:
        """
        Render an image using specified camera and save under provided file name.
        Optional format_override can be used to ignore format list from config file.
        Uses cached render from _init_render method.
        """
        if not self.cache:
            logger.info(f"Rendering {file_name}...")
            self._init_render(camera)
            if not self.cache:
                return

        scene = bpy.context.scene
        scene.render.filepath = self.render_path + file_name
        formats = [format_override] if format_override else self.formats

        for format in formats:
            self._set_image_format(format)
            abs_path = scene.render.filepath + self.img_ext
            self._save_render(self.cache, abs_path)

    def thumbnail(
        self,
        camera: bpy.types.Object,
        file_name: str,
        format_override: Optional[str] = None,
    ) -> None:
        """
        Make thumbnail copy of a rendered image. Uses previously saved render image data.
        Uses cached render from _init_render method.
        """
        if not self.cache:
            logger.info(f"Rendering {file_name}...")
            self.cache = self._init_render(camera)
            if not self.cache:
                return

        scene = bpy.context.scene
        scene.render.filepath = self.render_path + file_name
        formats = [format_override] if format_override else self.formats

        for format in formats:
            self._set_image_format(format)
            abs_path = scene.render.filepath + "_thumbnail" + self.img_ext

            new_render = self.cache.copy()
            new_render.scale(self.tmb_x, self.tmb_y)
            self._save_render(new_render, abs_path)
            bpy.data.images.remove(new_render)

    def render_animation(self, camera: bpy.types.Object, file_name) -> None:
        """
        Render sequence of images iterating over frame count range from bpy.context.scene.
        Clears cache after each frame as they are not supposed to be rendered as mutliple format.
        """
        scene = bpy.context.scene
        for frame in range(scene.frame_start, scene.frame_end + 1):
            frame_name = f"{file_name}_{frame:04}"
            scene.frame_set(frame)
            self.render(camera, frame_name, CACHE_FORMAT)
            self.clear_cache()

    def clear_cache(self):
        """
        Remove render cache file. Looks for CACHE_NAME files. Sets cache attribute to None.
        """
        logger.debug("Removing cached render.")
        if not config.blendcfg["SETTINGS"]["KEEP_PNGS"]:
            remove_file(self.cache_path)
        self.cache = None


class FFmpegWrapper:
    """Class responsible for running FFMPEG commands to sequence series of images to common video formats."""

    """Format specific codecs and other parameters"""
    FORMAT_ARGUMENTS = {
        "WEBM": {
            "-c:v": "libvpx-vp9",
            "-pix_fmt": "yuva420p",
            "-b:v": "5M",
        },
        "MP4": {
            "-c:v": "libx264",
            "-pix_fmt": "yuv420p",
            "-b:v": "5M",
            "-movflags": "+faststart",
        },
        "MPEG": {
            "-c:v": "mpeg2video",
            "-pix_fmt": "yuv420p",
            "-b:v": "5M",
        },
        "AVI": {
            "-c:v": "libx264",
            "-pix_fmt": "yuv420p",
            "-b:v": "5M",
        },
        "GIF": {},
    }

    def __init__(self) -> None:
        self.formats = config.blendcfg["SETTINGS"]["VIDEO_FORMAT"]
        self.format = None
        self.vid_ext = None
        self.img_ext = bpy.context.scene.render.file_extension
        self.res_x = config.blendcfg["SETTINGS"]["VIDEO_WIDTH"]
        self.res_y = config.blendcfg["SETTINGS"]["VIDEO_HEIGHT"]
        self.tmb_x = config.blendcfg["SETTINGS"]["THUMBNAIL_WIDTH"]
        self.tmb_y = config.blendcfg["SETTINGS"]["THUMBNAIL_HEIGHT"]
        self.fps = config.blendcfg["SETTINGS"]["FPS"]
        self.animation_path = config.animations_path
        self.render_path = config.renders_path

    def _set_video_format(self, format: str) -> None:
        """Set sequencer video output format and file extension."""
        self.format = format
        self.vid_ext = f".{self.format.lower()}"

    def run(self, input_file: str, output_file: str) -> None:
        """Run FFPMEG and sequence images into full-scale animation."""
        for format in self.formats:
            self._set_video_format(format)
            input_dict = {
                "-i": f"{self.render_path}{input_file}_%04d.png",
                "-framerate": str(self.fps),
                "-s": f"{self.res_x}x{self.res_y}",
            }
            self._sequence(input_dict, output_file)

    def reverse(self, input_file: str, output_file: str) -> None:
        """Reverse existing video file."""
        for format in self.formats:
            self._set_video_format(format)
            input_dict = {
                "-i": f"{self.animation_path}{input_file}{self.vid_ext}",
                "-vf": "reverse",
            }
            self._sequence(input_dict, output_file)

    def thumbnail(self, input_file: str, output_file: str) -> None:
        """Scale existing video file down into thumbnail."""
        for format in self.formats:
            self._set_video_format(format)
            input_dict = {
                "-i": f"{self.animation_path}{input_file}{self.vid_ext}",
                "-vf": f"scale={self.tmb_x}:{self.tmb_y}",
            }
            self._sequence(input_dict, output_file, suffix="_thumbnail")

    def _sequence(
        self,
        input_dict: Dict[str, str],
        output_file: str,
        suffix: str = "",
    ) -> None:
        """Execute FFMPEG command."""

        preset_dict = FFmpegWrapper.FORMAT_ARGUMENTS[self.format]
        full_output_file = Path(
            f"{self.animation_path}{output_file}{suffix}{self.vid_ext}"
        )

        mkdir(str(full_output_file.parent))
        cmd = self._get_cmd(input_dict | preset_dict, full_output_file)
        execute_cmd(cmd, stdout=True, stderr=True)
        logger.info(f"Sequenced (FFMPEG): {full_output_file}")

    def _get_cmd(self, cmd_dict: Dict[str, str], output_file: str) -> List[str]:
        """Prepare list of FFMPEG arguments from dictionary for subprocess library."""
        return (
            ["ffmpeg"]
            + [item for pair in cmd_dict.items() for item in pair]
            + [output_file]
            + ["-y"]
        )

    def clear_frames(self):
        """
        Remove frame files after sequencing.
        Recognizes <filename>_<frame_number>.<ext> filenames using regex.
        Expects 4-digit frame number.
        """
        logger.debug("Removing frames.")
        pattern = r"^.+_\d{4}..+$"
        if config.blendcfg["SETTINGS"]["KEEP_PNGS"]:
            return
        for file in listdir(self.render_path):
            if match(pattern, file):
                remove_file(self.render_path + file)
