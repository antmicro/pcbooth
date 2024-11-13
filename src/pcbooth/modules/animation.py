import bpy
import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu
import os
from math import radians, pi
import pcbooth.modules.camera as camera
from pcbooth.modules.light import Light
from mathutils import Vector
from subprocess import run
from random import randint
import logging

logger = logging.getLogger(__name__)


def clear_all_animation_action_data():
    for obj in bpy.data.objects:
        if obj.animation_data != None:
            obj.animation_data_clear()


def initial_objects_data_get(obj_init_location):
    # get object's initial location
    for obj in bpy.data.objects:
        obj_init_location[obj.name] = [
            obj.location.copy(),
            obj.rotation_euler.copy(),
            obj.hide_render,
            obj.hide_viewport,
        ]


def initial_objects_data_set(obj_init_location):
    # get object's initial location
    for obj in bpy.data.objects:
        if obj.name in obj_init_location.keys():
            obj.location = obj_init_location[obj.name][0]
            obj.rotation_euler = obj_init_location[obj.name][1]
            obj.hide_render = obj_init_location[obj.name][2]
            obj.hide_viewport = obj_init_location[obj.name][3]


def remove_pngs_website(dirpath):
    all_pngs = [
        file_name for file_name in os.listdir(dirpath) if file_name.endswith(".png")
    ]
    frame_pngs = sorted([file_name for file_name in all_pngs if ("frame" in file_name)])

    first = frame_pngs[0].split("_")
    name = first[0] + ".png"
    os.rename(dirpath + frame_pngs[0], dirpath + name)
    frame_pngs = frame_pngs[1:]

    last = frame_pngs[-1].split("_")
    name = last[1] + ".png"
    os.rename(dirpath + frame_pngs[-1], dirpath + name)
    frame_pngs = frame_pngs[:-1]

    for f in frame_pngs:
        os.remove(dirpath + f)


def find_or_new_fcurve(fcurves, data_pth, curve_count):
    if fcurves.find(data_pth) == None:
        for i in range(curve_count):
            fcurves.new(data_path=data_pth, index=i)
    return [fcurves.find(data_pth, index=i) for i in range(curve_count)]


# inter_type in ['LINEAR','BEZIER','CONSTANT'], values must be a list!
def add_keyframe(obj, frame, data_pth, inter_type, values):
    if obj.animation_data == None:
        obj.animation_data_create()
        obj.animation_data.action = bpy.data.actions.new(name=data_pth + "_" + obj.name)
    action = bpy.data.actions.get(obj.animation_data.action.name)
    fcs = find_or_new_fcurve(action.fcurves, data_pth, len(values))

    for i in range(len(values)):
        key = fcs[i].keyframe_points.insert(frame=frame, value=values[i])
        key.interpolation = inter_type


def hide_obj(obj, hide):
    obj.hide_render = hide
    obj.hide_viewport = hide
    # obj.hide_set(hide)
    obj.keyframe_insert(data_path="hide_render")
    obj.keyframe_insert(data_path="hide_viewport")


def get_object_volume(obj):
    bbox = cu.get_bbox(obj, "3d")
    x = [(a, b) for a in bbox for b in bbox if a.x == b.x and a != b][0]
    y = [(a, b) for a in bbox for b in bbox if a.y == b.y and a != b][0]
    z = [(a, b) for a in bbox for b in bbox if a.z == b.z and a != b][0]
    x = (x[0] - x[1]).length
    y = (y[0] - y[1]).length
    z = (z[0] - z[1]).length
    return x * y * z


def comp_place_rain_helper(obj_list, offset, interval, time_to_fall, frame_count):
    count_same_time_fall = randint(2, 4)
    for obj in obj_list:
        bpy.context.scene.frame_set(frame_count)
        hide_obj(obj, False)

        obj.location.z += offset
        obj.keyframe_insert(data_path="location")
        bpy.context.scene.frame_set(frame_count + time_to_fall)
        obj.location.z -= offset
        obj.keyframe_insert(data_path="location")

        count_same_time_fall -= 1
        if count_same_time_fall == 0:
            frame_count += interval
            count_same_time_fall = randint(2, 4)

    if count_same_time_fall != 0:
        frame_count += interval
    return frame_count


def comp_place_animation_rain(pcb_parent, scene, max_frame_count):
    # hide all components
    scene.frame_set(0)
    for obj in bpy.data.collections.get("Components").objects:
        hide_obj(obj, True)

    offset = 150
    interval = 3
    time_to_fall = 40
    frame_count = 1

    # PCB bottom components first
    pcb_parent.rotation_euler = Vector(pcb_parent.rotation_euler) + Vector((0, pi, 0))
    add_keyframe(
        pcb_parent,
        scene.frame_current,
        "rotation_euler",
        "CONSTANT",
        pcb_parent.rotation_euler[:],
    )

    bottom_obj = [
        obj
        for obj in bpy.data.collections.get("Components").objects
        if ("solder" not in obj.name) and (obj["PCB_Side"] == "B")
    ]
    top_obj = [
        obj
        for obj in bpy.data.collections.get("Components").objects
        if ("solder" not in obj.name) and (obj["PCB_Side"] == "T")
    ]

    frame_count = comp_place_rain_helper(
        sorted(bottom_obj, key=lambda x: get_object_volume(x)),
        offset,
        interval,
        time_to_fall,
        frame_count,
    )

    add_keyframe(
        pcb_parent,
        scene.frame_current,
        "rotation_euler",
        "LINEAR",
        pcb_parent.rotation_euler[:],
    )
    frame_count += time_to_fall * 2
    scene.frame_set(frame_count)
    # PCB top components second
    pcb_parent.rotation_euler = Vector(pcb_parent.rotation_euler) - Vector((0, pi, 0))
    add_keyframe(
        pcb_parent,
        scene.frame_current,
        "rotation_euler",
        "CONSTANT",
        pcb_parent.rotation_euler[:],
    )

    frame_count = comp_place_rain_helper(
        sorted(top_obj, key=lambda x: get_object_volume(x)),
        offset,
        interval,
        time_to_fall,
        frame_count,
    )

    frame_count += time_to_fall
    return frame_count + interval


def get_designator_from_obj_name(name):
    des_with_number = name.split(":")[0]
    return "".join([c for c in des_with_number if not c.isdigit()])


def comp_place_designator_helper(obj_list, offset, interval, time_to_fall, frame_count):
    last_designator = ""
    for obj in sorted(obj_list, key=lambda x: x.name):
        des = get_designator_from_obj_name(obj.name)
        if last_designator == "":
            last_designator = des
        if des != last_designator:
            last_designator = des
            frame_count += interval  # interval between new components appearing
        bpy.context.scene.frame_set(frame_count)
        hide_obj(obj, False)

        obj.location.z += offset
        obj.keyframe_insert(data_path="location")
        bpy.context.scene.frame_set(frame_count + time_to_fall)
        obj.location.z -= offset
        obj.keyframe_insert(data_path="location")
    return frame_count


def comp_place_animation_designator(pcb_parent, scene, max_frame_count):
    # hide all components
    scene.frame_set(0)
    for obj in bpy.data.collections.get("Components").objects:
        hide_obj(obj, True)
    offset = 150
    interval = 15
    time_to_fall = 40
    frame_count = 1

    bottom_obj = [
        obj
        for obj in bpy.data.collections.get("Components").objects
        if ("solder" not in obj.name) and (obj["PCB_Side"] == "B")
    ]
    top_obj = [
        obj
        for obj in bpy.data.collections.get("Components").objects
        if ("solder" not in obj.name) and (obj["PCB_Side"] == "T")
    ]

    # PCB bottom components first
    pcb_parent.rotation_euler = Vector(pcb_parent.rotation_euler) + Vector((0, pi, 0))
    add_keyframe(
        pcb_parent,
        scene.frame_current,
        "rotation_euler",
        "CONSTANT",
        pcb_parent.rotation_euler[:],
    )

    frame_count = comp_place_designator_helper(
        sorted(bottom_obj, key=lambda x: x.name),
        -offset,
        interval,
        time_to_fall,
        frame_count,
    )

    add_keyframe(
        pcb_parent,
        scene.frame_current,
        "rotation_euler",
        "LINEAR",
        pcb_parent.rotation_euler[:],
    )
    frame_count += time_to_fall * 2
    scene.frame_set(frame_count)
    # PCB top components second
    pcb_parent.rotation_euler = Vector(pcb_parent.rotation_euler) - Vector((0, pi, 0))
    add_keyframe(
        pcb_parent,
        scene.frame_current,
        "rotation_euler",
        "CONSTANT",
        pcb_parent.rotation_euler[:],
    )

    frame_count = comp_place_designator_helper(
        sorted(top_obj, key=lambda x: x.name),
        offset,
        interval,
        time_to_fall,
        frame_count,
    )

    frame_count += time_to_fall
    return frame_count + interval


def stackup_exploded_animation(pcb_parent, scene, max_frame_count):
    anim_length = 30
    offset = 10
    frame_count = 1

    # for name PCB_layerN (N=number) skip 'PCB_layer', sort by int(N)
    layers = [obj for obj in pcb_parent.children if obj.name.startswith("PCB_layer")]
    if len(layers) <= 1:
        return max_frame_count  # not enough layers
    time_to_seperate = int(anim_length / (len(layers) - 1))

    for obj in pcb_parent.children:
        # hide components and solder mesh
        if obj.type == "LIGHT" or obj.name.startswith("PCB_layer"):
            continue
        obj.hide_render = True
        obj.hide_viewport = True

    solder_switch_node = bpy.data.node_groups["Color_group"].nodes["Solder_Switch"]
    solder_switch_node.inputs[0].default_value = 1.0  # type: ignore

    sorted_layers = sorted(layers, key=lambda x: int(x.name[9:]))

    for i, layer in enumerate(sorted_layers):
        if i == 0:
            continue
        # start location
        scene.frame_set(frame_count)
        add_keyframe(
            layer, scene.frame_current, "location", "LINEAR", layer.location[:]
        )
        # end location
        scene.frame_set(frame_count + (len(sorted_layers) - 1) * time_to_seperate)
        layer.location += i * Vector((0, 0, offset))
        add_keyframe(
            layer, scene.frame_current, "location", "LINEAR", layer.location[:]
        )
        max_frame_count = max(max_frame_count, scene.frame_current)

    for light in bpy.data.collections.get("light").objects:
        if "layer" in light.name:
            continue
        # start location
        scene.frame_set(frame_count)
        add_keyframe(
            light, scene.frame_current, "location", "LINEAR", light.location[:]
        )
        # end location
        scene.frame_set(frame_count + i * time_to_seperate)
        light.location += i * Vector((0, 0, offset))
        add_keyframe(
            light, scene.frame_current, "location", "LINEAR", light.location[:]
        )

    anim_cam = [
        cam_class
        for cam_class in bpy.data.collections["camera"].objects
        if cam_class.name == "cam_anim"
    ][0]
    # copy photo camera rotation + location
    anim_cam.location = bpy.data.objects["camera_photo"].location
    anim_cam.rotation_euler = bpy.data.objects["camera_photo"].rotation_euler
    # start location
    scene.frame_set(frame_count)
    add_keyframe(
        anim_cam,
        scene.frame_current,
        "location",
        "LINEAR",
        anim_cam.location[:],
    )
    # end location
    scene.frame_set(frame_count + i * time_to_seperate)
    camera.set_to_view_PCB(anim_cam)
    add_keyframe(
        anim_cam,
        scene.frame_current,
        "location",
        "LINEAR",
        anim_cam.location[:],
    )

    # it's set to last frame
    top_layer_z = sorted_layers[-1].location.z
    # default values found for board with size 70x55x1.6
    # scales default values depending on difference in size of PCB
    pcbX = pcb_parent.dimensions.x
    pcbY = pcb_parent.dimensions.y
    scaleX = pcbX / 70
    scaleY = pcbY / 55
    energy_scale = max(scaleX, scaleY)
    light_energy = 50000
    light_size = 10
    light_color = (1, 1, 1)

    stackup_light1 = Light(
        "stackup_light1", "AREA", light_color, light_energy * (energy_scale**2)
    )
    stackup_light1.obj.location = (-pcbX * 1 / 2, -pcbY * 4 / 4, top_layer_z * 10 / 10)
    stackup_light1.obj.rotation_euler = (radians(70), radians(-50), radians(-20))
    stackup_light1.obj.data.size = light_size * energy_scale

    stackup_light2 = Light(
        "stackup_light2", "AREA", light_color, light_energy * (energy_scale**2)
    )
    stackup_light2.obj.location = (pcbX * 6 / 11, -pcbY * 5 / 4, top_layer_z * 11 / 10)
    stackup_light2.obj.rotation_euler = (radians(-240), radians(130), radians(30))
    stackup_light2.obj.data.size = light_size * energy_scale

    # add light energy interpolation <- to keep first frame identical to render
    scene.frame_set(frame_count + int(time_to_seperate))
    add_keyframe(
        stackup_light1.obj,
        scene.frame_current,
        "data.energy",
        "LINEAR",
        [stackup_light1.obj.data.energy],
    )
    add_keyframe(
        stackup_light2.obj,
        scene.frame_current,
        "data.energy",
        "LINEAR",
        [stackup_light1.obj.data.energy],
    )
    scene.frame_set(frame_count)
    stackup_light1.obj.data.energy = 0
    stackup_light2.obj.data.energy = 0
    add_keyframe(
        stackup_light1.obj,
        scene.frame_current,
        "data.energy",
        "LINEAR",
        [stackup_light1.obj.data.energy],
    )
    add_keyframe(
        stackup_light2.obj,
        scene.frame_current,
        "data.energy",
        "LINEAR",
        [stackup_light1.obj.data.energy],
    )

    # stackup_light3 = Light('stackup_light3','AREA',light_color,light_energy*(energy_scale**2))
    # stackup_light3.obj.location = (pcbX*1/2,-pcbY*3/2,top_layer_z*2/5)
    # stackup_light3.obj.rotation_euler = (radians(100),radians(75),radians(30))
    # stackup_light3.obj.data.size = light_size*energy_scale

    # # set lights parent to camera
    # bpy.ops.object.select_all(action='DESELECT')
    # stackup_light1.obj.select_set(True)
    # stackup_light2.obj.select_set(True)
    # stackup_light3.obj.select_set(True)
    # anim_cam_class.obj.select_set(True)
    # bpy.context.view_layer.objects.active = anim_cam_class.obj #active obj will be parent
    # bpy.ops.object.parent_set(keep_transform=True)
    # bpy.ops.object.select_all(action='DESELECT')

    return max_frame_count


def make_camera_for_rotation(scene):  # returns empty obj
    top_cam_anim = camera.create_camera(
        bpy.data.collections["camera"], "ANIM", (radians(60), radians(0), radians(13))
    )
    scene.camera = top_cam_anim

    bpy.ops.object.empty_add(
        type="PLAIN_AXES", align="WORLD", location=(0, 0, 0), scale=(1, 1, 1)
    )
    # to rotate camera around Z axis rotate empty in Z
    empty = bpy.context.selected_objects[0]

    bpy.ops.object.select_all(action="DESELECT")
    top_cam_anim.select_set(True)
    empty.select_set(True)
    bpy.context.view_layer.objects.active = empty  # active obj will be parent
    bpy.ops.object.parent_set(keep_transform=True)
    bpy.ops.object.select_all(action="DESELECT")
    return empty


def camera_rotation_animation(
    pcb_parent, scene, obj, angles, max_frame_count
):  # obj = camera parent (empty)
    frame_count = 0
    interval = 45

    while frame_count <= max_frame_count:
        for a in angles:
            scene.frame_set(frame_count)
            obj.rotation_euler.z += radians(a)
            add_keyframe(
                obj, frame_count, "rotation_euler", "LINEAR", obj.rotation_euler
            )
            frame_count += interval
        frame_count -= interval  # comment line to have pause between looped rotations

    return frame_count if max_frame_count == 0 else max_frame_count


def oval_camera_animation(
    pcb_parent, scene, obj, max_frame_count
):  # obj = camera object
    frame_count = 0
    anim_length = 300
    curve_rotation_euler = Vector((0, radians(25), 0))

    curveData = bpy.data.curves.new("CameraCurveData", type="CURVE")
    curveData.dimensions = "3D"
    curveData.resolution_u = 16
    curveData.path_duration = anim_length

    line = curveData.splines.new("NURBS")
    line.points.add(3)
    line.use_endpoint_u = True
    line.use_cyclic_u = True
    line.use_endpoint_u = False
    line.order_u = 4

    curveOB = bpy.data.objects.new("CameraCurve", curveData)
    scene.collection.objects.link(curveOB)

    # add FOLLOW_PATH constraint
    con = obj.constraints.new("FOLLOW_PATH")
    con.target = curveOB
    curveOB.data.use_path = True
    # generate FOLLOW_PATH animation
    anim = curveOB.data.animation_data_create()
    anim.action = bpy.data.actions.new("CameraCurveAction")
    fcu = anim.action.fcurves.new("eval_time")
    mod = fcu.modifiers.new("GENERATOR")
    mod.use_restricted_range = True
    mod.frame_start = frame_count
    mod.frame_end = frame_count + anim_length

    scale = 5.2
    point = cu.get_bbox(pcb_parent, "3d")[0]
    a = scale * (abs(point[0]) + abs(point[1])) / 2
    line.points[0].co = [a, a, 0, 1]
    line.points[1].co = [a, -a, 0, 1]
    line.points[2].co = [-a, -a, 0, 1]
    line.points[3].co = [-a, a, 0, 1]

    obj.location = (0, 0, 0)
    # add TRACK_TO constraint
    con_track = obj.constraints.new("TRACK_TO")
    con_track.target = pcb_parent

    curveOB.rotation_euler = curve_rotation_euler

    # bpy.ops.object.select_all(action='DESELECT')
    # cu.select_PCB()
    # bpy.ops.view3d.camera_to_view_selected()
    # bpy.ops.object.select_all(action='DESELECT')

    return frame_count + anim_length


def led_on_animation(pcb_parent, scene, max_frame_count):
    for mat in bpy.data.materials:
        if mat.node_tree != None:
            for m in mat.node_tree.nodes:
                if "Principled BSDF" in m.name:
                    saved_val = m.inputs["Emission Strength"].default_value + 0
                    m.inputs["Emission Strength"].default_value = 0
                    m.inputs["Emission Strength"].keyframe_insert(
                        data_path="default_value", frame=0
                    )
                    m.inputs["Emission Strength"].keyframe_insert(
                        data_path="default_value", frame=max_frame_count
                    )
                    m.inputs["Emission Strength"].default_value = saved_val
                    m.inputs["Emission Strength"].keyframe_insert(
                        data_path="default_value", frame=max_frame_count + 10
                    )

                    action = bpy.data.actions.get(
                        mat.node_tree.animation_data.action.name
                    )
                    fcu = [
                        f for f in action.fcurves if "Principled BSDF" in f.data_path
                    ][0]
                    for key in fcu.keyframe_points:
                        key.interpolation = "CONSTANT"
    max_frame_count += 40
    return max_frame_count


# used only for ANIMATIONS, OHP renders use different functions
def render_and_sequence(frame_count, anim_name="animation", keep_last_frame=False):
    keep_pngs = config.blendcfg["SETTINGS"]["KEEP_PNGS"]
    scene = bpy.context.scene
    scene.frame_start = 0
    scene.frame_end = frame_count
    scene.frame_current = 0
    logger.debug(f"Animation '{anim_name}' length: {frame_count}")

    # render pngs of each frame
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = config.anim_path + "frame"
    # scene.render.resolution_x = 2880 # hardcoded for special needs
    # scene.render.resolution_y = 1620 # hardcoded for special needs
    bpy.ops.render.render(animation=True)  # render each frame as png

    # combine pngs into video
    anim_fps = int(config.blendcfg["SETTINGS"]["FPS"])
    anim_width = int(config.blendcfg["SETTINGS"]["WIDTH"])
    anim_height = int(config.blendcfg["SETTINGS"]["HEIGHT"])
    anim_width_thumb = int(config.blendcfg["SETTINGS"]["THUMBNAIL_WIDTH"])
    anim_height_thumb = int(config.blendcfg["SETTINGS"]["THUMBNAIL_HEIGHT"])
    webm_path = f"{config.anim_path}{anim_name}.webm"
    webm_path_thumb = f"{config.anim_path}{anim_name}_thumbnail.webm"
    anim_path = config.anim_path
    logger.info("Combining pngs to video...")
    cmd = f"ffmpeg -y -loglevel error -stats -framerate {anim_fps} -f image2 -i {anim_path}frame%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -s {anim_width}x{anim_height} -b:v 5M {webm_path}"
    run(cmd, shell=True)
    if config.blendcfg["SETTINGS"]["THUMBNAILS"]:
        cmd = f"ffmpeg -y -loglevel error -stats -framerate {anim_fps} -f image2 -i {anim_path}frame%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -s {anim_width_thumb}x{anim_height_thumb} -b:v 5M {webm_path_thumb}"
        run(cmd, shell=True)
    logger.info("Done")
    # removed already used pngs
    if not keep_pngs:
        all_pngs = [
            file_name
            for file_name in os.listdir(config.anim_path)
            if file_name.endswith(".png")
        ]
        frame_pngs = sorted(
            [file_name for file_name in all_pngs if ("frame" in file_name)]
        )
        if keep_last_frame and len(frame_pngs):
            os.rename(
                config.anim_path + frame_pngs[-1], config.anim_path + anim_name + ".png"
            )
            frame_pngs = frame_pngs[:-1]
        for f in frame_pngs:
            os.remove(config.anim_path + f)
    clear_all_animation_action_data()


def make_animations(pcb_parent, add_info):
    logger.info("** [ANIMATION] **")

    scene = bpy.context.scene

    camera_parent = make_camera_for_rotation(scene)
    # max_frame_count was used to use multiple animations at once, now each animation is separate
    max_frame_count = 0
    # max_frame_count = max(max_frame_count, count_from_anim)

    obj_init_location = dict()
    initial_objects_data_get(obj_init_location)

    if config.blendcfg["ANIMATION"]["COMP_PLACE"]:
        count_from_anim = comp_place_animation_designator(
            pcb_parent, scene, max_frame_count
        )
        render_and_sequence(count_from_anim, "comp_place")
        initial_objects_data_set(obj_init_location)
    elif config.blendcfg["ANIMATION"]["COMP_RAIN"]:
        count_from_anim = comp_place_animation_rain(pcb_parent, scene, max_frame_count)
        render_and_sequence(count_from_anim, "comp_rain")
        initial_objects_data_set(obj_init_location)

    if config.blendcfg["ANIMATION"]["CAMERA360"]:
        count_from_anim = camera_rotation_animation(
            pcb_parent, scene, camera_parent, [0, 90, 90, 90, 90], max_frame_count
        )
        render_and_sequence(count_from_anim, "camera360")
        initial_objects_data_set(obj_init_location)
    elif config.blendcfg["ANIMATION"]["CAMERA180"]:
        count_from_anim = camera_rotation_animation(
            pcb_parent, scene, camera_parent, [0, 90, 90, -90, -90], max_frame_count
        )
        render_and_sequence(count_from_anim, "camera180")
        initial_objects_data_set(obj_init_location)
    elif config.blendcfg["ANIMATION"]["CAMERA_OVAL"]:
        count_from_anim = oval_camera_animation(
            pcb_parent, scene, camera_parent.children[0], max_frame_count
        )
        render_and_sequence(count_from_anim, "camera_oval")
        initial_objects_data_set(obj_init_location)

    if config.blendcfg["ANIMATION"]["STACKUP_EXPLODE"]:
        count_from_anim = stackup_exploded_animation(pcb_parent, scene, max_frame_count)
        render_and_sequence(count_from_anim, "stackup", True)
        initial_objects_data_set(obj_init_location)
        solder_switch_node = bpy.data.node_groups["Color_group"].nodes["Solder_Switch"]
        solder_switch_node.inputs[0].default_value = 0.0  # type: ignore
        for obj in pcb_parent.children:
            # show components and solder mesh
            if obj.type == "LIGHT":
                continue
            obj.hide_render = False
            obj.hide_viewport = False
    if config.blendcfg["ANIMATION"]["LED_ON"]:
        count_from_anim = led_on_animation(pcb_parent, scene, max_frame_count)
        render_and_sequence(count_from_anim, "led_on")
        initial_objects_data_set(obj_init_location)

    bpy.data.objects.remove(camera_parent.children[0])  # camera
    bpy.data.objects.remove(camera_parent)


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
