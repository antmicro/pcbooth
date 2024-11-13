import bpy
import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu

# from animation import *
from pcbooth.modules.renderer import (
    render_animation,
    stdout_redirected,
    ffmpeg_sequencer,
    make_stills,
    make_thumbnail,
    remove_pngs,
    get_files,
)
from pcbooth.modules.studio import obj_set_rotation
from pathlib import Path
from math import radians
import pcbooth.modules.camera as camera
from pcbooth.modules.light import Light
from mathutils import Matrix, Vector, Euler
import logging

logger = logging.getLogger(__name__)


def make_stackup(pcb_parent):
    logger.info("*** RENDERING STACKUP ***")
    scene = bpy.context.scene
    layers = [child for child in pcb_parent.children if "PCB_layer" in child.name]
    sorted_layers = sorted(layers, key=lambda x: int(x.name[9:]))
    if len(sorted_layers) <= 1:
        logger.warning("Not enough layers found in model to render stackup.")
        return  # not enough layers

    y_offset = int(pcb_parent.dimensions.y / 20)
    offset = Vector((0, y_offset, 10))
    layer_light_epsilon = Vector((0, 0, 0.001))
    layer_light_mult = 8
    original_light_mult = 0.5

    solder_switch_node = bpy.data.node_groups["Color_group"].nodes["Solder_Switch"]
    solder_switch_node.inputs[0].default_value = 1.0  # type: ignore

    # hide all components
    for obj in bpy.data.collections.get("Components").objects:
        if obj.type == "LIGHT":
            continue
        obj.hide_render = True
        obj.hide_viewport = True

    # hide solder mesh
    solder = bpy.data.objects.get("Solder")
    if solder is not None:
        solder.hide_render = True
        solder.hide_viewport = True

    anim_cam = camera.create_camera(
        bpy.data.collections["camera"], "ANIM", (radians(54.2), 0, 0)
    )
    scene.camera = anim_cam
    for i, layer in enumerate(sorted_layers):
        if i == (len(sorted_layers) - 1):
            i -= 1
        if i == 0:
            continue
        layer.location += i * offset

    # light of top layer
    original_lights = []
    for light in bpy.data.collections.get("light").objects:
        if "layer" in light.name:
            light.data.energy *= layer_light_mult
            continue
        original_lights.append(light)
        light.location += i * offset  # i from for loop above
        light.data.energy *= original_light_mult
    top_layer_light = bpy.data.objects[sorted_layers[0].name + "_light_top"]
    bot_layer_light = bpy.data.objects[sorted_layers[-1].name + "_light_bot"]

    new_spot_light = Light("spot_light", "SPOT", (1, 1, 1), 20).obj
    new_spot_light.data.spot_size = 3.14159  # int(pcb_parent.dimensions.x/10)
    new_spot_light.rotation_euler = (radians(60), 0, 0)
    mid_layer = sorted_layers[int(len(sorted_layers) / 2)]
    new_spot_light.location = mid_layer.location - Vector(
        (0, mid_layer.dimensions.y / 2, 0)
    )
    matrix = Matrix.LocRotScale(None, Euler(new_spot_light.rotation_euler), None)
    new_spot_light.location += matrix @ Vector([0, 0, mid_layer.dimensions.x])
    new_spot_light.data.energy *= abs(
        new_spot_light.location.y * new_spot_light.location.z
    )
    top_layer_light.select_set(True)
    # now original is selected
    bpy.ops.object.duplicate()
    # now duplicate is selected
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    new_top_light = bpy.context.selected_objects[0]
    new_top_light.name = sorted_layers[-1].name + "_light_top"
    cu.link_obj_to_collection(new_top_light, bpy.data.collections.get("light"))
    new_top_light.location = (
        Vector(
            (
                0,
                sorted_layers[-1].location.y,
                sorted_layers[-1].location.z + pcb_parent.dimensions.z,
            )
        )
        + layer_light_epsilon
    )
    bpy.context.view_layer.objects.active = sorted_layers[-1]
    bpy.ops.object.parent_set(keep_transform=True)
    bpy.ops.object.select_all(action="DESELECT")
    bot_layer_light.select_set(True)
    # now original is selected
    bpy.ops.object.duplicate()
    # now duplicate is selected
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    new_bot_light = bpy.context.selected_objects[0]
    new_bot_light.name = sorted_layers[0].name + "_light_bot"
    cu.link_obj_to_collection(new_bot_light, bpy.data.collections.get("light"))

    new_bot_light.location = (
        Vector((0, sorted_layers[0].location.y, sorted_layers[0].location.z))
        - layer_light_epsilon
    )
    bpy.context.view_layer.objects.active = sorted_layers[0]
    bpy.ops.object.parent_set(keep_transform=True)
    bpy.ops.object.select_all(action="DESELECT")

    camera.set_to_view_PCB(anim_cam)

    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = int(config.blendcfg["SETTINGS"]["WIDTH"])
    scene.render.resolution_y = int(config.blendcfg["SETTINGS"]["HEIGHT"])
    for i, layer in enumerate(reversed(sorted_layers)):
        scene.render.filepath = config.anim_path + "layer" + str(i)

        with stdout_redirected():
            bpy.ops.render.render(write_still=True)
        ofile = scene.render.filepath + ".png"
        if Path(ofile).exists():
            logger.info(f"Render layer {i+1}/{len(sorted_layers)}: Saved as: {ofile}")
        else:
            logger.error(f"Render layer {i+1}/{len(sorted_layers)}: Failed!")

        make_thumbnail(config.anim_path + "layer" + str(i) + ".png")
        layer.hide_render = True
        layer.hide_viewport = True
        bpy.data.objects[layer.name + "_light_bot"].hide_render = True
        bpy.data.objects[layer.name + "_light_bot"].hide_viewport = True
        bpy.data.objects[layer.name + "_light_top"].hide_render = True
        bpy.data.objects[layer.name + "_light_top"].hide_viewport = True
        if i == 0:
            continue
        for light in original_lights:
            light.location -= offset

    # revert scene to the state before this function

    # show all components
    for obj in bpy.data.collections.get("Components").objects:
        if obj.type == "LIGHT":
            continue
        obj.hide_render = False
        obj.hide_viewport = False

    if solder is not None:
        solder.hide_render = False
        solder.hide_viewport = False

    solder_switch_node.inputs[0].default_value = 0.0  # type: ignore

    for i, layer in enumerate(sorted_layers):
        layer.hide_render = False
        layer.hide_viewport = False
        if i == (len(sorted_layers) - 1):
            i -= 1
        if i == 0:
            continue
        layer.location -= i * offset

    for light in bpy.data.collections.get("light").objects:
        if "layer" in light.name:
            light.data.energy /= layer_light_mult
        light.hide_render = False
        light.hide_viewport = False

    for light in original_lights:
        light.data.energy /= original_light_mult

    bpy.data.objects.remove(new_top_light)
    bpy.data.objects.remove(new_bot_light)
    bpy.data.objects.remove(new_spot_light)
    bpy.data.objects.remove(anim_cam)
    return


# TRANSITION ANIMATIONS -------------------------------------------------------
def get_camera_positions(obj, focus, options):
    def _get_camera_data(option, camera_data):
        obj_set_rotation(obj, option[-1])
        cam = bpy.data.objects["camera_" + option[:-1]]
        camera_data[option + "_loc"] = Vector(cam.location).copy()
        camera_data[option + "_rot"] = Euler(cam.rotation_euler).to_quaternion()
        camera_data[option + "_focus_loc"] = Vector(focus.location).copy()
        camera_data[option + "_fstop"] = cam.data.dof.aperture_fstop

    camera_data = {}
    obj_set_rotation(obj, "T")
    logger.debug(options)
    for c in options:
        _get_camera_data(c, camera_data)
    obj_set_rotation(obj, "T")
    return camera_data


def create_curve_object(camAloc, camBloc):
    # create curve to serve as path for camera movement
    curveData = bpy.data.curves.new("CameraCurveData", type="CURVE")
    curveData.dimensions = "3D"
    curveData.resolution_u = 16
    curveData.path_duration = int(config.blendcfg["SETTINGS"]["FPS"])

    # calculate curve points
    point1 = camAloc + (camBloc - camAloc) * 3 / 10
    point2 = camAloc + (camBloc - camAloc) * 7 / 10
    line = curveData.splines.new("NURBS")
    line.points.add(3)
    line.use_endpoint_u = True
    line.order_u = 4
    line.points[0].co = list(camAloc) + [1]
    line.points[1].co = list(point1.normalized() * point1.length * 1.75) + [1]
    line.points[2].co = list(point2.normalized() * point2.length * 1.75) + [1]
    line.points[3].co = list(camBloc) + [1]

    # create object out of curve
    curve_obj = bpy.data.objects.new("CameraCurve", curveData)
    curve_obj.data.use_path = True
    bpy.context.scene.collection.objects.link(curve_obj)

    # prepare animation daata
    animation_data = curve_obj.data.animation_data_create()
    animation_data.action = bpy.data.actions.new("CameraCurveAction")
    fcurve = animation_data.action.fcurves.new("eval_time")
    curve_modifier = fcurve.modifiers.new("GENERATOR")
    curve_modifier.use_restricted_range = True
    curve_modifier.frame_start = 0
    curve_modifier.frame_end = int(config.blendcfg["SETTINGS"]["FPS"])

    return curve_obj


def prepare_transition_animation_keyframes(pcb_parent, options, original_pcb_rot):
    scene = bpy.context.scene
    frame_count = int(config.blendcfg["SETTINGS"]["FPS"])
    scene.frame_start = 0
    scene.frame_end = frame_count
    pos1 = options[0]
    pos2 = options[1]

    # create animation camera
    cam_anim = camera.create_camera(bpy.data.collections["camera"], "animation")
    camera.set_focus(cam_anim, pcb_parent)
    cam_anim_focus = cam_anim.children[0]
    cam_anim_focus.parent = None  # unparent focus obj
    cam_anim.rotation_mode = "QUATERNION"

    # save locations of the cameras in start and end positions
    camera_data = get_camera_positions(pcb_parent, cam_anim_focus, options)
    camAloc = camera_data[pos1 + "_loc"].copy()
    camBloc = camera_data[pos2 + "_loc"].copy()
    camArot = camera_data[pos1 + "_rot"].copy()
    camBrot = camera_data[pos2 + "_rot"].copy()
    camArot.make_compatible(camBrot)

    # create NURBS curve object to serve as camera path
    curve_obj = create_curve_object(camAloc, camBloc)

    # apply curve as path constraint
    cam_constraint = cam_anim.constraints.new("FOLLOW_PATH")
    cam_constraint.target = curve_obj

    # reset animation camera location
    cam_anim.location = (0, 0, 0)

    # calculating keyframes
    scene.frame_set(0)
    cam_anim_focus.location = camera_data[pos1 + "_focus_loc"]
    cam_anim_focus.keyframe_insert(data_path="location")
    cam_anim.data.dof.aperture_fstop = camera_data[pos1 + "_fstop"]
    cam_anim.data.keyframe_insert(data_path="dof.aperture_fstop")

    obj_set_rotation(pcb_parent, pos1[-1:], original_pcb_rot)
    pcb_parent.keyframe_insert(data_path="rotation_euler")
    cam_anim.rotation_quaternion = camArot
    cam_anim.keyframe_insert(data_path="rotation_quaternion")
    scale = 2
    scene.frame_set(int(frame_count / 2))
    cam_anim.data.dof.aperture_fstop = min(
        camera_data[pos1 + "_fstop"], camera_data[pos2 + "_fstop"]
    ) / (2 * scale)
    cam_anim.data.keyframe_insert(data_path="dof.aperture_fstop")
    scene.frame_set(int(frame_count / 5))
    cam_anim.data.dof.aperture_fstop = (
        min(camera_data[pos1 + "_fstop"], camera_data[pos2 + "_fstop"]) / scale
    )
    cam_anim.data.keyframe_insert(data_path="dof.aperture_fstop")
    cam_anim_focus.location = (camAloc + camBloc) / 4
    cam_anim_focus.keyframe_insert(data_path="location")
    scene.frame_set(int(frame_count * 4 / 5))
    cam_anim.data.dof.aperture_fstop = (
        min(camera_data[pos1 + "_fstop"], camera_data[pos2 + "_fstop"]) / scale
    )
    cam_anim.data.keyframe_insert(data_path="dof.aperture_fstop")
    cam_anim_focus.location = (camAloc + camBloc) / 4
    cam_anim_focus.keyframe_insert(data_path="location")

    for i in range(1, frame_count + 1):
        scene.frame_set(i)
        cam_anim.rotation_quaternion = (
            camArot.slerp(camBrot, i / frame_count)
            if pos1[:-1] != pos2[:-1]
            else camArot
        )
        cam_anim.keyframe_insert(data_path="rotation_quaternion")

    cam_anim_focus.location = camera_data[pos2 + "_focus_loc"]
    cam_anim_focus.keyframe_insert(data_path="location")
    cam_anim.data.dof.aperture_fstop = camera_data[pos2 + "_fstop"]
    cam_anim.data.keyframe_insert(data_path="dof.aperture_fstop")
    obj_set_rotation(pcb_parent, pos2[-1:], original_pcb_rot)
    pcb_parent.keyframe_insert(data_path="rotation_euler")
    scene.frame_current = 0


def get_views(views, sides, all=True):
    pairs = []
    for view1 in views:
        for side1 in sides:
            for view2 in views:
                for side2 in sides:
                    reduced = (view1 == view2 and side1 != side2) or (
                        view1 != view2 and side1 == side2
                    )
                    if (
                        (view1 + side1) != (view2 + side2)
                        and (view1 + side1, view2 + side2) not in pairs
                        and (view2 + side2, view1 + side1) not in pairs
                        and (all or reduced)
                    ):
                        pairs.append((view1 + side1, view2 + side2))
    return pairs


def make_rotation(pcb_parent, options):
    camAside_camBside = options[0] + "_" + options[1]
    original_pcb_rot = Vector(pcb_parent.rotation_euler).copy()
    prepare_transition_animation_keyframes(pcb_parent, options, original_pcb_rot)

    cam_anim = bpy.data.objects.get("cam_animation")
    render_animation(cam_anim, camAside_camBside)
    make_stills(options[0], options[1])

    logger.info("***   FRAME SEQUENCER   ***")
    animations = get_files(camAside_camBside)
    for animname in animations:
        reversename = "_".join(reversed(animname.split("_")))
        logger.info(f"Sequencing with ffmpeg: {animname} / {reversename}")
        ffmpeg_sequencer(animname, reversename, thumbnail=False)
        ffmpeg_sequencer(animname, reversename, thumbnail=True)

    for animname in animations:
        if not config.blendcfg["SETTINGS"]["KEEP_PNGS"]:
            remove_pngs(animname)
            logger.info("Deleted frames.")
    bpy.data.objects.remove(cam_anim)
    pcb_parent.rotation_euler = original_pcb_rot


def make_transitions(pcb_parent, add_info):
    logger.info("** [PORTAL TRANSITIONS] **")
    match config.blendcfg["OUTPUT"]["TRANSITIONS"][1]:
        case "Iso":
            pairs = get_views(["iso"], ["T", "B", "R"], all=True)
        case "All":
            pairs = get_views(["ortho", "left", "right"], ["T", "B"], all=False)
        case "Renders":
            # add T, B and R to sides list based on what's in config
            sides = [
                opt[0]
                for opt in config.blendcfg["RENDERS"]
                if config.blendcfg["RENDERS"][opt] and opt in ["TOP", "BOTTOM", "REAR"]
            ]
            # add to camera views list based on what's in config
            # ISO camera is excluded as it's orthographic camera and can't transition to other cameras
            views = []
            for opt in [
                opt_true
                for opt_true in config.blendcfg["RENDERS"]
                if config.blendcfg["RENDERS"][opt_true]
            ]:
                if opt in ["TOP", "BOTTOM", "REAR", "ISO"]:
                    continue
                if bpy.data.objects.get(f"camera_{opt.lower()}") is None:
                    logger.warning(
                        f"Transition with {opt.lower()} view enabled in config but no 'camera_{opt.lower()}' object found in file. Skipping transition."
                    )
                    continue
                views.append(opt.lower())
            pairs = get_views(views, sides)
    for idx, pair in enumerate(pairs):
        camera.update_all_camera_location(pcb_parent)
        # rendering frames
        logger.info(f"***   RENDERING: {pair[0]}_{pair[1]}   {idx+1}/{len(pairs)}***")
        make_rotation(pcb_parent, list(pair))


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
