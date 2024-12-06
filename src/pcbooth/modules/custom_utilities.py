"""Module containing custom utilities functions."""

import bpy
from mathutils import Matrix
from math import radians
import logging
from typing import List

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


def apply_all_transforms(object: bpy.types.Object) -> None:
    """Apply all translations to specified object"""
    object.select_set(True)
    bpy.ops.object.transform_apply()
    object.select_set(False)


def center_on_scene(object: bpy.types.Object) -> None:
    """
    Move object's origin point to its geometric center and move the object to point (0,0,0) on scene.
    This is needed for nice animations when object is being rotated about the origin point.
    """
    object.select_set(True)
    bpy.context.view_layer.objects.active = object
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    object.location[:] = [0, 0, 0]
    bpy.ops.object.select_all(action="DESELECT")
    apply_all_transforms(object)


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


def select_all(parent_obj: bpy.types.Object) -> None:
    """Select parent object and all children recursively"""
    bpy.context.view_layer.objects.active = parent_obj
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.object.select_grouped(extend=True, type="CHILDREN_RECURSIVE")
    parent_obj.select_set(True)
    return bpy.context.selected_objects


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
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        parent.select_set(True)
        bpy.context.view_layer.objects.active = parent  # active obj will be parent
        bpy.ops.object.parent_set(keep_transform=True)
        bpy.ops.object.select_all(action="DESELECT")


def link_obj_to_collection(
    obj: bpy.types.Object, target_coll: bpy.types.Collection
) -> None:
    """Loop through all collections the obj is linked to and unlink it from there, then link to targed collection."""
    for coll in obj.users_collection:  # type: ignore
        coll.objects.unlink(obj)
    target_coll.objects.link(obj)


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


def hex_to_rgb(hex_number: str) -> tuple[float, ...]:
    """Convert hex number to RGBA."""
    rgb = []
    for i in (0, 2, 4):
        decimal = int(hex_number[i : i + 2], 16)
        rgb.append(decimal / 255)
    return tuple(rgb)


def add_empty(name: str, target_coll: bpy.types.Collection = None) -> bpy.types.Object:
    """
    Add empty object to the scene. If no target collection is specified, link to root scene collection.
    """
    object = bpy.data.objects.new(name, None)
    if target_coll:
        link_obj_to_collection(object, target_coll)
    else:
        bpy.context.scene.collection.objects.link(object)
    return object


def set_origin(object: bpy.types.Object):
    object.select_set(True)
    bpy.context.view_layer.objects.active = object
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    bpy.ops.object.select_all(action="DESELECT")


def clear_animation_data():
    """
    Remove any animation data if it was added by the job.
    TODO: for now this will remove all existing actions, so there needs to be some way
            to backup user predefined keyframes
    """
    logger.debug("Clearing animation data.")
    for action in bpy.data.actions:
        bpy.data.actions.remove(action)
