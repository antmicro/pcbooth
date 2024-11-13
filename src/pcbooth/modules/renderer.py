import bpy
import pcbooth.modules.config as config
import addon_utils
from math import radians
import logging
import os
import sys
from pathlib import Path
from contextlib import contextmanager
from subprocess import run
from wand.image import Image
import shutil
import re


# https://blender.stackexchange.com/questions/6119/suppress-output-of-python-operators-bpy-ops
@contextmanager
def stdout_redirected(to=os.devnull):
    """
    import os

    with stdout_redirected(to=filename):
        print("from Python")
        os.system("echo non-Python applications are also supported")
    """
    fd = sys.stdout.fileno()

    ##### assert that Python and C stdio write using the same file descriptor
    ####assert libc.fileno(ctypes.c_void_p.in_dll(libc, "stdout")) == fd == 1

    def _redirect_stdout(to):
        sys.stdout.close()  # + implicit flush()
        os.dup2(to.fileno(), fd)  # fd writes to 'to' file
        sys.stdout = os.fdopen(fd, "w")  # Python writes to fd

    with os.fdopen(os.dup(fd), "w") as old_stdout:
        with open(to, "w") as file:
            _redirect_stdout(to=file)
        try:
            yield  # allow code to be run with the redirected stdout
        finally:
            _redirect_stdout(to=old_stdout)  # restore stdout.
            # buffering and flags such as
            # CLOEXEC may be different


logger = logging.getLogger(__name__)


def set_freestyle(line_thickness=1, use_fills=True):
    logger.info("Setting up freestyle")
    bpy.data.scenes["Scene"].display.shading.light = "FLAT"
    addon_utils.enable("render_freestyle_svg")
    bpy.context.scene.render.use_freestyle = True
    bpy.context.scene.svg_export.use_svg_export = True
    bpy.context.scene.render.line_thickness = line_thickness
    bpy.context.scene.svg_export.object_fill = use_fills
    bpy.data.linestyles["LineStyle"].use_export_fills = True
    bpy.data.linestyles["LineStyle"].use_export_strokes = True
    bpy.data.linestyles["LineStyle"].caps = "ROUND"
    bpy.context.scene.view_layers["ViewLayer"].freestyle_settings.crease_angle = (
        radians(162)
    )
    bpy.context.scene.view_layers["ViewLayer"].freestyle_settings.linesets[
        "LineSet"
    ].select_edge_mark = True

    # bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    # bpy.context.scene.render.film_transparent = False


def setup_ultralow_cycles():
    bpy.context.scene.cycles.samples = 1
    bpy.context.scene.cycles.use_denoising = False
    bpy.context.scene.cycles.max_bounces = 0
    # bpy.context.scene.cycles.blur_glossy = 1
    bpy.context.scene.cycles.caustics_reflective = False
    bpy.context.scene.cycles.caustics_refractive = False
    bpy.context.scene.cycles.use_adaptive_sampling = False
    bpy.context.scene.world.cycles_visibility.camera = False
    bpy.context.scene.world.cycles_visibility.diffuse = False
    bpy.context.scene.world.cycles_visibility.glossy = False
    bpy.context.scene.world.cycles_visibility.transmission = False
    bpy.context.scene.world.cycles_visibility.scatter = False


def revert_cycles():
    bpy.context.scene.cycles.samples = int(
        config.blendcfg["SETTINGS"]["CYCLES_SAMPLES"]
    )
    bpy.context.scene.cycles.use_denoising = True
    bpy.context.scene.cycles.max_bounces = max(
        [
            bpy.context.scene.cycles.diffuse_bounces,
            bpy.context.scene.cycles.glossy_bounces,
            bpy.context.scene.cycles.transmission_bounces,
            bpy.context.scene.cycles.sample_clamp_indirect,
        ]
    )
    # bpy.context.scene.cycles.blur_glossy = 1
    bpy.context.scene.cycles.caustics_reflective = True
    bpy.context.scene.cycles.caustics_refractive = True
    bpy.context.scene.cycles.use_adaptive_sampling = True
    bpy.context.scene.world.cycles_visibility.camera = True
    bpy.context.scene.world.cycles_visibility.diffuse = True
    bpy.context.scene.world.cycles_visibility.glossy = True
    bpy.context.scene.world.cycles_visibility.transmission = True
    bpy.context.scene.world.cycles_visibility.scatter = True


def compositing(set):
    """Compositing decorator, makes sure scene uses nodes and clears the current setup before changing it to another"""

    def _set_compositing():
        # turn nodes on
        bpy.context.scene.use_nodes = True
        tree = bpy.context.scene.node_tree

        # clear default nodes
        for node in tree.nodes:
            tree.nodes.remove(node)

        set()

    return _set_compositing


@compositing
def set_compositing():
    """Applies glare effect for standard board renders"""
    tree = bpy.context.scene.node_tree
    rend_layers_node = tree.nodes.new(type="CompositorNodeRLayers")
    rend_layers_node.location = -400, 0

    glare_node = tree.nodes.new(type="CompositorNodeGlare")
    glare_node.glare_type = "FOG_GLOW"
    glare_node.size = 5
    glare_node.location = 0, 0

    viewer_node = tree.nodes.new("CompositorNodeViewer")
    viewer_node.location = 400, -200

    comp_node = tree.nodes.new("CompositorNodeComposite")
    comp_node.location = 400, 200

    # link nodes
    links = tree.links
    links.new(rend_layers_node.outputs[0], glare_node.inputs[0])
    links.new(glare_node.outputs[0], viewer_node.inputs[0])
    links.new(glare_node.outputs[0], comp_node.inputs[0])


@compositing
def set_pads_compositing():
    """Used for overlaying PadLayer on ViewLayer on renders, PadLayer is added to component models using render_footprints.py"""
    tree = bpy.context.scene.node_tree

    rend_layers_main = tree.nodes.new(type="CompositorNodeRLayers")
    rend_layers_pads = tree.nodes.new(type="CompositorNodeRLayers")
    rend_layers_main.layer = "ViewLayer"
    rend_layers_pads.layer = "PadLayer"

    alpha_over = tree.nodes.new("CompositorNodeAlphaOver")
    alpha_over.inputs[0].default_value = 0.11

    viewer_node = tree.nodes.new("CompositorNodeViewer")
    comp_node = tree.nodes.new("CompositorNodeComposite")

    rend_layers_main.location = -400, 100
    rend_layers_pads.location = -400, -100
    alpha_over.location = 0, 0
    viewer_node.location = 400, -200
    comp_node.location = 400, 200

    # link nodes
    links = tree.links
    links.new(rend_layers_main.outputs[0], alpha_over.inputs[1])
    links.new(rend_layers_pads.outputs[0], alpha_over.inputs[2])
    links.new(alpha_over.outputs[0], comp_node.inputs[0])


@compositing
def set_hotarea_compositing():
    """Used for fast rendering of black & white, low-res hotarea shapes"""
    tree = bpy.context.scene.node_tree

    rend_layers_node = tree.nodes.new(type="CompositorNodeRLayers")
    comp_node = tree.nodes.new("CompositorNodeComposite")
    mix_node = tree.nodes.new(type="CompositorNodeMixRGB")
    rgb_white_node = tree.nodes.new(type="CompositorNodeRGB")
    rgb_black_node = tree.nodes.new(type="CompositorNodeRGB")
    rgb_white_node.outputs[0].default_value[:] = 0.6, 0.6, 0.6, 1
    rgb_black_node.outputs[0].default_value[:] = 0.0, 0.0, 0.0, 1
    rend_layers_node.location = -500, 100
    comp_node.location = 300, 0
    rgb_black_node.location = -200, -300
    rgb_white_node.location = -200, -100
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


def set_GPU(print_settings=False):
    scene = bpy.context.scene
    dev_type = "CUDA"  # acceleration device type to use, either CUDA or OPTIX
    bpy.context.preferences.addons["cycles"].preferences.compute_device_type = dev_type
    bpy.context.preferences.addons[
        "cycles"
    ].preferences.get_devices()  # let Blender detects GPU device
    device_types = [
        dev.type for dev in bpy.context.preferences.addons["cycles"].preferences.devices
    ]
    found_GPU = dev_type in device_types
    if not found_GPU:
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = (
            "NONE"
        )
    else:
        for d in bpy.context.preferences.addons["cycles"].preferences.devices:
            d.use = d.type == dev_type
    if print_settings:
        logger.info(
            f"Rendering units settings: {[{'name': dev.name, 'type': dev.type, 'use': dev.use} for dev in bpy.context.preferences.addons['cycles'].preferences.devices]}"
        )
    scene.cycles.device = "GPU" if found_GPU else "CPU"
    return found_GPU


def init_setup():
    if config.isComponent:
        set_pads_compositing()
    else:
        set_compositing()
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = int(config.blendcfg["SETTINGS"]["WIDTH"])
    scene.render.resolution_y = int(config.blendcfg["SETTINGS"]["HEIGHT"])
    scene.render.engine = "CYCLES"
    scene.render.use_persistent_data = True  # more memory used, faster renders
    set_GPU(True)
    # self.scene.cycles.tile_size = 4096
    scene.cycles.samples = config.blendcfg["SETTINGS"]["CYCLES_SAMPLES"]
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces[0].clip_start = 0.1  # fix Z fight in viewport


def render(cam_obj, file_name):
    scene = bpy.context.scene
    scene.camera = cam_obj
    scene.render.filepath = file_name

    with stdout_redirected():
        bpy.ops.render.render(write_still=True)
    ofile = scene.render.filepath + ".png"
    if Path(ofile).exists():
        logger.info(f"Render Completed: Saved as: {ofile}")
    else:
        logger.error(f"Render {file_name} failed!")


def render_animation(cam_obj, file_name):
    scene = bpy.context.scene
    scene.camera = cam_obj
    filename = config.anim_path + file_name + "_frame"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.cycles.samples = int(config.blendcfg["SETTINGS"]["CYCLES_SAMPLES"])
    scene.render.resolution_x = int(config.blendcfg["SETTINGS"]["WIDTH"])
    scene.render.resolution_y = int(config.blendcfg["SETTINGS"]["HEIGHT"])
    set_GPU()
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.render.filepath = filename + f"{frame:04}"
        scene.frame_set(frame)
        with stdout_redirected():
            bpy.ops.render.render(write_still=True)
        ofile = scene.render.filepath + ".png"
        if Path(ofile).exists():
            logger.info(f"Frame {frame}/{scene.frame_end}: Saved as: {ofile}")
        else:
            logger.error(f"Frame {frame}/{scene.frame_end}: Failed")


def ffmpeg_sequencer(animname, reversename, thumbnail=False, reverse=True):
    FPS = int(config.blendcfg["SETTINGS"]["FPS"])
    if thumbnail:
        X_res = int(config.blendcfg["SETTINGS"]["THUMBNAIL_WIDTH"])
        Y_res = int(config.blendcfg["SETTINGS"]["THUMBNAIL_HEIGHT"])
    else:
        X_res = int(config.blendcfg["SETTINGS"]["WIDTH"])
        Y_res = int(config.blendcfg["SETTINGS"]["HEIGHT"])

    thumbname = "_thumbnail" if thumbnail else ""
    cmd = f"ffmpeg -loglevel error -stats -framerate {FPS} -f image2 -i {config.anim_path}{animname}_frame%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -s {X_res}x{Y_res} -b:v 5M {config.anim_path}{animname}{thumbname}.webm"
    reverse_cmd = f"ffmpeg -loglevel error -stats -c:v libvpx-vp9 -i {config.anim_path}{animname}{thumbname}.webm -pix_fmt yuva420p -vf reverse -b:v 5M {config.anim_path}{reversename}{thumbname}.webm"
    if os.path.isfile(config.anim_path + animname + thumbname + ".webm"):
        os.remove(config.anim_path + animname + thumbname + ".webm")
    run(cmd, shell=True)
    if reverse:
        if os.path.isfile(config.anim_path + reversename + thumbname + ".webm"):
            os.remove(config.anim_path + reversename + thumbname + ".webm")
        run(reverse_cmd, shell=True)


def make_thumbnail(img_path):
    if config.blendcfg["SETTINGS"]["THUMBNAILS"]:
        with Image(filename=img_path) as img:
            with img.clone() as thumbnail:
                thumbnail_path = img_path.replace(".png", "_thumbnail.png")
                thumbnail.thumbnail(
                    config.blendcfg["SETTINGS"]["THUMBNAIL_WIDTH"],
                    config.blendcfg["SETTINGS"]["THUMBNAIL_HEIGHT"],
                )
                thumbnail.save(filename=thumbnail_path)
                logger.info(f"Saved: '{thumbnail_path}'")


# saves first and last frame as still image render
def make_stills(view1, view2):
    dirpath = config.anim_path
    anim_basename = view1 + "_" + view2
    start, end = get_start_end_frames(dirpath, anim_basename)

    shutil.copy(
        dirpath + anim_basename + f"_frame{start:04d}.png", dirpath + view1 + ".png"
    )
    shutil.copy(
        dirpath + anim_basename + f"_frame{end:04d}.png",
        dirpath + view2 + ".png",
    )
    make_thumbnail(dirpath + view1 + ".png")
    make_thumbnail(dirpath + view2 + ".png")


def get_start_end_frames(dirpath, basename):
    files = os.listdir(dirpath)
    pattern = re.compile(rf"{basename}" + r"_frame(\d{4})\.png")
    frames = []
    for file in files:
        match = pattern.match(file)
        logger.debug(match)
        if match:
            frames.append(int(match.group(1)))
    if frames:
        start = min(frames)
        end = max(frames)
        return start, end
    return 0, 0


def get_files(animname, reverse=True):
    files = [
        file
        for file in os.listdir(config.anim_path)
        if "frame" in file and animname in file
    ]
    animation = set("_".join(file.split("_")[-3:-1]) for file in files)
    return animation


# this should be in animation module?
# removes all frames for specified animation name group
def remove_pngs(animname):
    dirpath = config.anim_path
    for file in os.listdir(dirpath):
        if animname in file and "frame" in file and file.endswith(".png"):
            os.remove(dirpath + file)


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
