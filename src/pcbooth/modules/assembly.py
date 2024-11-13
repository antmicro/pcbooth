import bpy
from mathutils import Vector
import logging
from pcbooth.modules.custom_utilities import get_bbox
import pcbooth.modules.config as config
import pcbooth.modules.camera as camera
from pcbooth.modules.hotareas import (
    component_hotareas,
    run_hotareas_script,
    setup_ultralow_cycles,
)
from pcbooth.modules.renderer import (
    revert_cycles,
    render_animation,
    ffmpeg_sequencer,
    remove_pngs,
    make_stills,
    get_files,
)
import pcbooth.modules.custom_utilities as cu
import os

logger = logging.getLogger(__name__)


def add_empty(obj) -> bpy.types.Object:
    """Prepare empty to be used as target for copy location constraint"""
    bbox_centre = get_bbox(obj, "centre")
    bpy.ops.object.empty_add(location=bbox_centre)
    empty = bpy.data.objects["Empty"]
    empty.select_set(True)
    bpy.ops.object.transform_apply()
    return empty


def add_constraint(obj, target, center_z, max_z):
    """Add copy location constraint to obj using target"""
    diff = obj.location.z - center_z
    constraint = obj.constraints.new(type="COPY_LOCATION")
    constraint.use_x = False
    constraint.use_y = False
    constraint.use_offset = True
    constraint.target = target
    if diff < 0:
        constraint.invert_z = True
    constraint.influence = abs(diff) / max_z


def make_explode_keyframes(empty, pcb_parent, spread):
    """Add keyframe for exploded view"""
    frame_count = int(config.blendcfg["SETTINGS"]["FPS"])
    empty.keyframe_insert(data_path="location", frame=1)
    spread = spread
    empty.location += Vector([0, 0, spread])
    empty.keyframe_insert(data_path="location", frame=frame_count)


def animate_camera(pcb_parent, frame):
    cameras = [cam for cam in bpy.data.objects if cam.type == "CAMERA"]
    bpy.context.scene.frame_set(frame)
    camera.update_all_camera_location(pcb_parent)
    for cam in cameras:
        cam.keyframe_insert(data_path="location", frame=frame)


def make_constraint_setup(empty, pcb_parent):
    """Add constraints to all children of parent object"""
    max_z = pcb_parent.dimensions.z
    center_z = get_bbox(pcb_parent, "centre").z
    for obj in pcb_parent.children:
        add_constraint(obj, empty, center_z, max_z)


def render_and_process_animation(
    active_camera, cam_type, frameA, frameB, start_frame, end_frame
):
    render_animation(active_camera, f"{frameA}_{frameB}")
    make_stills(frameA, frameB)

    logger.info("***   FRAME SEQUENCER   ***")
    animations = get_files(f"{frameA}_{frameB}")
    for animname in animations:
        reversename = "_".join(reversed(animname.split("_")))
        logger.info(f"Sequencing with ffmpeg: {animname} / {reversename}")
        ffmpeg_sequencer(animname, reversename, thumbnail=False)
        ffmpeg_sequencer(animname, reversename, thumbnail=True)

    for animname in animations:
        if not config.blendcfg["SETTINGS"]["KEEP_PNGS"]:
            remove_pngs(animname)
            logger.info("Deleted frames.")

    # if camera type not specified in animation file name, add it
    # used in assembly animations; not relevant to standard transitions
    if cam_type is not None:
        for file in os.listdir(config.anim_path):
            if (
                not any(ctype.lower() in file for ctype in config.cam_types.keys())
                and "view" in file
            ):
                os.rename(
                    config.anim_path + file, config.anim_path + f"{cam_type}_" + file
                )


def make_explodedview(pcb_parent, add_info):
    logger.info("** [EXPLODED VIEW] **")
    bpy.context.view_layer.objects.active = pcb_parent

    # add generated explode animation if no keyframes are defined in assembly
    if not cu.check_keyframes_exist():
        logger.info("No defined keyframes found, generating default ones.")
        empty = add_empty(pcb_parent)
        make_constraint_setup(empty, pcb_parent)
        make_explode_keyframes(empty, pcb_parent, 40)
        bpy.ops.wm.save_as_mainfile(filepath=config.pcb_blend_path)
    else:
        logger.info("Found existing keyframes.")

    # calculate last frame in case user defined custom one
    frames = cu.get_keyframes()
    start_frame = min(frames)
    end_frame = max(frames)

    bpy.context.scene.frame_start = start_frame
    bpy.context.scene.frame_end = end_frame

    for frame in reversed(frames):
        animate_camera(pcb_parent, frame)

    # temporary hardcoded names to avoid problems with matching them to webpages frontend
    frameA = "view1"
    frameB = "view2"

    direction = ["TOP", "BOTTOM"]
    for dir in direction:
        # if direction is to be rendered
        if config.blendcfg["RENDERS"][dir]:
            # check each camera type
            for cam_type in config.cam_types:
                # if given camera is to be rendered
                if config.blendcfg["RENDERS"][cam_type]:
                    logger.info(f"rendering assembly from {dir} {cam_type} camera")
                    cam_obj = bpy.data.objects.get("camera_" + cam_type.lower())
                    if cam_obj is None:
                        logger.warning(
                            f"{cam_type} view enabled in config but no 'camera_{cam_type.lower()}' object found in file. Skipping animation render."
                        )
                        continue
                    render_and_process_animation(
                        cam_obj,
                        cam_type.lower(),
                        frameA,
                        frameB,
                        start_frame,
                        end_frame,
                    )
                    if config.blendcfg["OUTPUT"]["HOTAREAS"]:
                        logger.info(f"rendering hotarea {dir} {cam_type}")
                        # set ultralow cycles
                        setup_ultralow_cycles()
                        # for assemblies top and bottom components are treated equaly
                        components = [obj for obj in config.top_components]
                        bpy.context.scene.frame_set(start_frame)
                        component_hotareas(
                            frameA,
                            components,
                            config.hotareas_path + f"{cam_type.lower()}_{frameA}",
                            cam_obj,
                        )
                        bpy.context.scene.frame_set(end_frame)
                        component_hotareas(
                            frameB,
                            components,
                            config.hotareas_path + f"{cam_type.lower()}_{frameB}",
                            cam_obj,
                        )
                        revert_cycles()
                        run_hotareas_script(config.hotareas_path)
