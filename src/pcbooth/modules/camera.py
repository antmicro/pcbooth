import bpy
from pcbooth.modules.custom_utilities import select_PCB, link_obj_to_collection, get_bbox
import pcbooth.modules.config as config
from math import radians, acos, sin
from mathutils import Vector, Matrix, Euler


camera_positions = {
    "PHOTO": (radians(38), radians(0), radians(13)),
    "PERSP": (radians(60), radians(0), radians(20)),
    "LEFT": (radians(190), radians(-156), radians(-197)),
    "FRONT": (radians(30), radians(0), radians(0)),
    "RIGHT": (radians(200), radians(-205), radians(-155)),
    "ORTHO": (radians(0), radians(0), radians(0)),
    "ISO": (radians(54.736), radians(0), radians(45)),
}


def determine_lens() -> int:
    """
    Determine camera lens based on config effect enabled
    105 is perspective camera
    2000 yields orthographic renders
    """
    if config.blendcfg["EFFECTS"]["TRUE_ORTHO"]:
        return 2000
    else:
        return 105


def create_preset_camera(cameraCol, type):
    rotation = camera_positions[type]
    name = "camera_" + type.lower()
    camera = bpy.data.cameras.new(name)
    camera.type = "PERSP"
    camera.lens = determine_lens()
    camera.clip_start = 0.1
    camera.clip_end = 10000  # set long clip end for renders

    camera_obj = bpy.data.objects.new(name, camera)
    camera_obj.rotation_euler = rotation
    link_obj_to_collection(camera_obj, cameraCol)
    set_to_view_PCB(camera_obj)

    return camera_obj


def add_cameras(pcb_parent):
    cameraCol = bpy.data.collections.new("camera")
    bpy.context.scene.collection.children.link(cameraCol)
    for item in camera_positions.keys():
        create_preset_camera(cameraCol, item)

    if config.blendcfg["EFFECTS"]["DEPTH_OF_FIELD"]:
        for camera_object in cameraCol.objects:
            focus_obj = set_focus(camera_object, pcb_parent)
            if focus_obj:
                link_obj_to_collection(focus_obj, cameraCol)

    bpy.context.scene.collection.children.unlink(cameraCol)
    return cameraCol


def create_camera(cameraCol, Type, rotation=(0, 0, 0)):
    name = "cam_" + Type.lower()
    cam = bpy.data.cameras.new(name)
    cam_obj = bpy.data.objects.new(name, cam)
    cam.type = "PERSP"
    cam.lens = determine_lens()

    link_obj_to_collection(cam_obj, cameraCol)
    cam.clip_start = 0.1  # fix Z fight in viewport
    cam.clip_end = 10000  # set long clip end for renders

    cam_obj.rotation_euler = rotation
    set_to_view_PCB(cam_obj)

    return cam_obj


def set_to_view_PCB(cam_obj):
    select_PCB()
    bpy.context.scene.camera = cam_obj
    bpy.ops.view3d.camera_to_view_selected()
    bpy.ops.object.select_all(action="DESELECT")
    cam_obj.location *= 1.05


def update_all_camera_location(pcb):
    cameras = [
        cam_obj
        for cam_obj in bpy.data.collections["camera"].objects
        if cam_obj.name != "cam_animation"
    ]
    cam_obj = bpy.data.objects.get("camera_custom")
    if cam_obj is not None:
        cameras.append(cam_obj)
    for cam_obj in cameras:
        if cam_obj.type != "CAMERA":
            continue
        set_to_view_PCB(cam_obj)

        if config.blendcfg["EFFECTS"]["DEPTH_OF_FIELD"]:
            set_focus(cam_obj, pcb)


def set_focus(cam_obj, focus_on_obj):
    if cam_obj.type != "CAMERA":
        return None
    cam = cam_obj.data
    cam.dof.use_dof = True

    # cameras child is its .dof.focus_object
    if len(cam_obj.children) > 0:
        empty_obj = cam_obj.children[0]
    else:
        empty_obj = bpy.data.objects.new(cam_obj.name + "_focus", None)
        bpy.context.scene.collection.objects.link(empty_obj)
        empty_obj.empty_display_size = 2
        empty_obj.empty_display_type = "PLAIN_AXES"

        empty_obj.select_set(True)
        cam_obj.select_set(True)
        bpy.context.view_layer.objects.active = cam_obj  # active obj will be parent
        bpy.ops.object.parent_set(keep_transform=True)
        bpy.ops.object.select_all(action="DESELECT")

    bbox = get_bbox(focus_on_obj, "3d")
    focus_matrix = Matrix.LocRotScale(
        focus_on_obj.location, Euler(focus_on_obj.rotation_euler), focus_on_obj.scale
    )
    focus_matrix_inverted = focus_matrix.inverted()
    bbox = [focus_matrix_inverted @ v for v in bbox]
    bbox = filter(lambda v: v[2] > 0, bbox)  # vector.z > 0
    bbox = sorted(bbox, key=lambda v: abs((v - cam_obj.location).length))
    bbox = [focus_matrix @ v for v in bbox]

    edge_middle = (bbox[0] + bbox[1]) / 2
    # 2 points far from camera, between edge middle and corner
    focus_end = (bbox[2] + 3 * bbox[3]) / 2

    empty_obj.location = (3 * edge_middle + focus_end) / 4

    edge_middle_cam_vec = Vector(edge_middle - cam_obj.location).normalized()
    focus_end_cam_vec = Vector(focus_end - cam_obj.location).normalized()
    cos_focus_angle = edge_middle_cam_vec.dot(focus_end_cam_vec)  # cos(alfa)
    sin_focus_angle = sin(acos(cos_focus_angle))
    tan_focus_angle = sin_focus_angle / cos_focus_angle

    # radious in meters
    aperture_radius = tan_focus_angle * (Vector(edge_middle - cam_obj.location).length)
    # Apertures radius = (lens mm / aperture fstop) / 200
    # (200 is conversion from diameter to radius and meters at same time)
    fstop = cam.lens / (aperture_radius * 3)  # 15 instead of 200 for less blur

    cam.dof.aperture_fstop = fstop
    cam.dof.focus_object = empty_obj
    # cam.dof.focus_distance = abs((focus_obj.location-obj.location).length)
    return empty_obj


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
