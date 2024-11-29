"""World, scene and render engine setup and rendering handler functions module."""

import bpy
import logging
from pathlib import Path
from wand.image import Image
from typing import Callable, Tuple
from pcbooth.modules.file_io import stdout_redirected, execute_cmd
import pcbooth.modules.config as config
from typing import Dict, List, Callable


logger = logging.getLogger(__name__)


def setup_ultralow_cycles() -> Tuple[bpy.types.PropertyGroup, bpy.types.PropertyGroup]:
    """
    Configure the Cycles render engine for ultra-low quality and to minimize the time required to render an image.
    Returns backup properties as a tuple.
    """
    cycles_backup = bpy.context.scene.cycles.copy()
    cycles_visibility_backup = bpy.context.scene.world.cycles_visibility.copy()

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

    return (cycles_backup, cycles_visibility_backup)


def revert_cycles(cycles_backup, cycles_visibility_backup) -> None:
    """Restore Cycles setup from backup data."""
    bpy.context.scene.cycles = cycles_backup
    bpy.context.scene.world.cycles_visibility = cycles_visibility_backup


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
    rgb_white_node.outputs[0].default_value[:] = 0.6, 0.6, 0.6, 1
    rgb_black_node.outputs[0].default_value[:] = 0.0, 0.0, 0.0, 1

    links = tree.links
    links.new(
        rend_layers_node.outputs["Alpha"],
        mix_node.inputs[0],
    )
    links.new(
        rgb_white_node.outputs["RGBA"],
        mix_node.inputs[1],
    )
    links.new(
        rgb_black_node.outputs["RGBA"],
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


def init_renderer():
    """Setup initial renderer properties."""
    logger.info("Setting up renderer...")
    scene = bpy.context.scene
    renderer = bpy.context.scene.render

    renderer.image_settings.file_format = config.blendcfg["SETTINGS"]["IMAGE_FORMAT"]
    assign_color_mode()

    renderer.resolution_x = int(config.blendcfg["SETTINGS"]["IMAGE_WIDTH"])
    renderer.resolution_y = int(config.blendcfg["SETTINGS"]["IMAGE_HEIGHT"])

    renderer.engine = "CYCLES"
    renderer.film_transparent = True
    renderer.use_file_extension = True
    # renderer.use_persistent_data = True  # more memory used, faster renders

    scene.frame_start = 1
    scene.frame_end = int(config.blendcfg["SETTINGS"]["FPS"])
    scene.cycles.samples = config.blendcfg["SETTINGS"]["SAMPLES"]
    scene.cycles.use_denoising = True

    set_default_compositing()
    setup_gpu()


def assign_color_mode() -> None:
    """
    Assign color mode based on currently set file format. Defaults to RGBA,
    if the chosen format doesn't support transparency, fallbacks to RGB
    """
    try:
        bpy.context.scene.render.image_settings.color_mode = "RGBA"
    except TypeError:
        bpy.context.scene.render.image_settings.color_mode = "RGB"


def render(camera: bpy.types.Object, file_name: str) -> None:
    """Render an image using specified camera and save under provided file name."""
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.filepath = config.renders_path + file_name
    ext = scene.render.file_extension
    abs_path = scene.render.filepath + ext

    logger.info(f"Rendering {file_name}{ext}...")
    with stdout_redirected():
        bpy.ops.render.render(write_still=True)

    if Path(abs_path).exists():
        logger.info(f"Render completed, saved as: {bpy.path.relpath(abs_path)}")
    else:
        logger.error(f"Render failed for {bpy.path.relpath(abs_path)}")


def render_animation(camera: bpy.types.Object, file_name: str) -> None:
    """Render sequence of images iterating over frame count range from bpy.context.scene"""
    scene = bpy.context.scene
    for frame in range(scene.frame_start, scene.frame_end + 1):
        frame_name = f"{file_name}_{frame:04}"
        scene.frame_set(frame)
        render(camera, frame_name)


def make_thumbnail(filepath: str) -> None:
    """Make thumbnail copy of an image."""
    ext = bpy.context.scene.render.file_extension

    image_path = filepath + ext
    thumbnail_path = filepath + "_thumbnail" + ext
    width = config.blendcfg["SETTINGS"]["THUMBNAIL_WIDTH"]
    height = config.blendcfg["SETTINGS"]["THUMBNAIL_HEIGHT"]

    with Image(filename=image_path) as img, img.clone() as thumbnail:
        thumbnail.thumbnail(width, height)
        thumbnail.save(filename=thumbnail_path)
        logger.info(f"Prepared thumbnail: {thumbnail_path}")


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
        self.format = config.blendcfg["SETTINGS"]["VIDEO_FORMAT"]
        self.vid_ext = f".{self.format.lower()}"
        self.img_ext = bpy.context.scene.render.file_extension
        self.res_x = config.blendcfg["SETTINGS"]["VIDEO_WIDTH"]
        self.res_y = config.blendcfg["SETTINGS"]["VIDEO_HEIGHT"]
        self.tmb_x = config.blendcfg["SETTINGS"]["THUMBNAIL_WIDTH"]
        self.tmb_y = config.blendcfg["SETTINGS"]["THUMBNAIL_HEIGHT"]
        self.fps = config.blendcfg["SETTINGS"]["FPS"]

    def run(self, input_file: str, output_file: str) -> None:
        """Run FFPMEG and sequence images into full-scale animation."""
        input_dict = {
            "-i": f"{config.renders_path}{input_file}_%04d{self.img_ext}",
            "-framerate": str(self.fps),
            "-s": f"{self.res_x}x{self.res_y}",
        }
        self._sequence(input_dict, output_file)

    def reverse(self, input_file: str, output_file: str) -> None:
        """Reverse existing video file."""
        input_dict = {
            "-i": f"{config.animations_path}{input_file}{self.vid_ext}",
            "-vf": "reverse",
        }
        self._sequence(input_dict, output_file)

    def thumbnail(self, input_file: str, output_file: str) -> None:
        """Scale existing video file down into thumbnail."""
        input_dict = {
            "-i": f"{config.animations_path}{input_file}{self.vid_ext}",
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
        full_output_file = (
            f"{config.animations_path}{output_file}{suffix}{self.vid_ext}"
        )

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
