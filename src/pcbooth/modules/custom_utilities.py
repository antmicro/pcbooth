import bpy
from mathutils import Vector, kdtree
import logging
import pcbooth.modules.config as config
from math import radians
from mathutils import Matrix
from typing import List, Tuple

logger = logging.getLogger(__name__)


def save_pcb_blend(path: str, apply_transforms: bool = False) -> None:
    """Save the current model at the specified path."""
    if apply_transforms:
        for obj in bpy.context.scene.objects:
            apply_all_transforms(obj)
    bpy.ops.wm.save_as_mainfile(filepath=path)


def open_blendfile(blendfile: str) -> None:
    """Open a given .blend file.

    Equivalent to file/open in GUI, will overwrite current file!
    """
    logger.info(f"Opening existing file: {blendfile}")
    bpy.ops.wm.open_mainfile(filepath=blendfile)


def get_top_bottom_component_lists(
    objects: List[bpy.types.Object] = [], enable_all: bool = False
) -> Tuple[bpy.types.Object, bpy.types.Object]:
    """
    Get top and bottom component lists using char stored in 'PCB_Side' custom property.
    This custom property is saved in objects when they're imported using picknblend tool.
    If `enable_all` argument is set to true, all available components passed to function will be added to both of the lists.
    """
    top_comps = []
    bot_comps = []
    if enable_all:
        top_comps = [obj for obj in objects if obj.name != "BBOX"]
        bot_comps = top_comps.copy()
    else:
        components = bpy.data.collections.get("Components")
        if not components:
            return top_comps, bot_comps
        for comp in components.objects:
            if "PCB_Side" not in comp.keys():
                continue
            if comp["PCB_Side"] == "T":
                top_comps.append(comp)
            elif comp["PCB_Side"] == "B":
                bot_comps.append(comp)
    logger.debug(f"Read top components: {top_comps}")
    logger.debug(f"Read bot components: {bot_comps}")
    return top_comps, bot_comps


def get_min_z(object: bpy.types.Object) -> float:
    """Get lowest Z coordinate of all bounding box vertices coordinates of an object"""
    current_vertices = [Vector(v[:]) @ object.matrix_world for v in object.bound_box]
    return min([v.z for v in current_vertices])


def center_on_scene(object: bpy.types.Object) -> None:
    """
    Move object's origin point to its geometric center and move the object to point (0,0,0) on scene.
    This is needed for nice animations when object is being rotated about the origin point.
    """
    object.select_set(True)
    bpy.context.view_layer.objects.active = object
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    object.location[:] = [0, 0, 0]
    apply_all_transforms(object)
    bpy.ops.object.select_all(action="DESELECT")


def rotate_horizontally(object: bpy.types.Object) -> None:
    """
    Apply rotation based on PCB dimensions to rotate it horizontally.
    Rotation is applied around center of a scene (0,0,0) point.
    """
    rotation_matrix = Matrix.Rotation(radians(-90), 4, "Z")
    if object.dimensions.x < object.dimensions.y:
        logger.info("Rotating the PCB horizontally.")
        object.rotation_euler = [0, 0, radians(-90)]
        apply_all_transforms(object)

        # rotate camera_custom object if present
        if custom_camera := bpy.data.objects.get("camera_custom"):
            logger.info("Rotating 'camera_custom' accordingly")
            custom_camera.matrix_world = rotation_matrix @ custom_camera.matrix_world


def apply_display_rot(object: bpy.types.Object, display_rot: int) -> None:
    """
    Apply rotation based on DISPLAY_ROT property in component model.
    DISPLAY_ROT property can be used to ensure the model appears in upright position on render (usually when looking at the marking).
    """
    logger.info(f"Rotating model using DISPLAY_ROT property ({display_rot}deg)")
    rotation = radians(display_rot)
    object.rotation_euler = [0, 0, rotation]
    apply_all_transforms(object)


def update_depsgraph():
    """Update Blender dependency graph tree. Needed to refresh translation matrix of an object."""
    bpy.context.view_layer.update()


def get_top_parent(object: bpy.types.Object) -> bpy.types.Object:
    """Find top parent of the child object"""
    while object.parent:
        object = object.parent
    return object


def get_root_object(object: bpy.types.Object) -> bpy.types.Object | None:
    """Get source object of the linked nested object structure"""
    library_name = object.library.name.replace(".blend", "")
    lib_obj = bpy.data.objects.get(library_name)
    return lib_obj


def parent_list_to_object(
    child_objs: List[bpy.types.Object],
    parent: bpy.types.Object,
    skip_lights: bool = True,
    skip_cameras: bool = True,
) -> None:
    """Parent all objects in a list to another object."""
    for obj in child_objs:
        if obj.parent is not None:
            continue
        if skip_lights and obj.type == "LIGHT":
            continue
        if skip_cameras and obj.type == "CAMERA":
            continue
        if obj.library:
            continue

        # set parent for all child objects
        obj.select_set(True)
        parent.select_set(True)
        bpy.context.view_layer.objects.active = parent  # active obj will be parent
        bpy.ops.object.parent_set(keep_transform=True)
        bpy.ops.object.select_all(action="DESELECT")


def apply_all_transforms(object: bpy.types.Object) -> None:
    """Apply all translations to specified object"""
    object.select_set(True)
    bpy.ops.object.transform_apply()
    object.select_set(False)


def select_all(parent_obj: bpy.types.Object) -> None:
    """Select parent object and all children recursively"""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")

    bpy.context.view_layer.objects.active = parent_obj
    bpy.ops.object.select_grouped(extend=True, type="CHILDREN_RECURSIVE")
    parent_obj.select_set(True)


def default_world() -> None:
    """Change Viewport before saving - help when opening model in GUI"""
    logger.info("Setting world to default")
    bpy.data.scenes["Scene"].display.shading.light = "STUDIO"
    bpy.context.scene.render.engine = "CYCLES"
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "SOLID"


def get_collection(
    name: str, parent: bpy.types.Collection = None
) -> bpy.types.Collection:
    """Get collection with provided name, create it if necessary"""

    name = name[:63]
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        if parent:
            parent.children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
    return col


def link_obj_to_collection(
    obj: bpy.types.Object, target_coll: bpy.types.Collection
) -> None:
    """Loop through all collections the obj is linked to and unlink it from there, then link to targed collection."""
    for coll in obj.users_collection:  # type: ignore
        coll.objects.unlink(obj)
    target_coll.objects.link(obj)


###


def get_parent_object(collection):
    """Get object out of collection that doesn't have any parent - this is the main object that has nested layers inside"""
    for object in collection.objects:
        if not object.parent:
            return object
    return None


# returns list of object's vertices with float precision =-1
def get_vertices(obj, precision=0):
    verts = [vert.co for vert in obj.data.vertices]
    plain_verts = [vert.to_tuple(precision) for vert in verts]
    return plain_verts


def make_kd_tree(verts):
    main_list = list(verts)
    kd = kdtree.KDTree(len(main_list))
    for i, v in enumerate(main_list):
        kd.insert(v, i)
    kd.balance()
    return kd


# remove set of vertices from another set
def get_verts_difference(main_set, remove_set):
    main_list = list(main_set)
    kd = make_kd_tree(main_list)
    indexes_to_remove = []
    for vert in remove_set:
        point, index, dist = kd.find(vert)
        if dist < 0.0001:  # points in the same place
            indexes_to_remove.append(index)

    for id in sorted(indexes_to_remove, reverse=True):
        main_list.pop(id)
    return main_list


# check if there are common vertices for two sets (using previously created kdtree)
def verts_in(kd, add_set):
    for vert in add_set:
        point, index, dist = kd.find(vert)
        if dist:
            if dist < 0.0001:  # points in the same place
                return True
    return False


# probably not used
def get_bbox(obj, arg):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    bbox_vert = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    if arg == "centre":  # finds current center point of the model
        #       centre = sum((Vector(b) for b in obj.bound_box), Vector())
        centre = sum(bbox_vert, Vector())
        centre /= 8
        return centre
    elif arg == "2d":
        corner2d = [corner.to_2d() for corner in bbox_vert]
        return corner2d[::2]
    elif arg == "3d":
        return bbox_vert


# calculates bounding box out of list of Vector(x,y,z)
# USED


# deprecated, use select_all instead
def select_PCB():
    # TODO: see if this can be written in same way as the non-PCB (with select_grouped)
    bpy.ops.object.select_all(action="DESELECT")
    if config.isPCB:
        board_col = bpy.data.collections.get("Board")
        if board_col is not None:
            for obj in board_col.objects:
                obj.select_set(True)
        comp_col = bpy.data.collections.get("Components")
        if comp_col is not None:
            for obj in comp_col.objects:
                obj.select_set("Annotations" not in obj.name)
    else:
        bpy.context.view_layer.objects.active = config.rendered_obj
        bpy.ops.object.select_grouped(extend=True, type="CHILDREN_RECURSIVE")
        config.rendered_obj.select_set(True)


def remove_collection(name):
    remCol = bpy.data.collections.get(name)
    if remCol is None:
        logger.debug(f"Did not find '{name}' collection to remove. Continue")
        return
    logger.debug(
        f"Found '{name}' collection. Removing its objects and whole collection."
    )
    for obj in remCol.objects:
        bpy.data.objects.remove(obj)
    bpy.data.collections.remove(remCol)


def link_obj_to_collection(
    obj: bpy.types.Object, target_coll: bpy.types.Collection
) -> None:
    """Loop through all collections the obj is linked to and unlink it from there, then link to targed collection."""
    for coll in obj.users_collection:  # type: ignore
        coll.objects.unlink(obj)
    target_coll.objects.link(obj)


def check_keyframes_exist():
    """Check if any keyframes are defined in the assembly"""
    keyframes = []
    for obj in bpy.context.scene.objects:
        if obj.animation_data and obj.animation_data.action:
            for fcurve in obj.animation_data.action.fcurves:
                keyframes.extend(fcurve.keyframe_points)
    return keyframes


def get_keyframes():
    """Find and sort all keyframes' indexes defined in scene"""
    frames = []
    for obj in bpy.context.scene.objects:
        if obj.animation_data and obj.animation_data.action:
            for fcurve in obj.animation_data.action.fcurves:
                for keyframe in fcurve.keyframe_points:
                    frame = keyframe.co[0]
                    if frame not in frames:
                        frames.append(int(frame))
    sorted_frames = sorted(frames)
    return sorted_frames


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
