"""Module containing custom utilities functions."""

import bpy
from mathutils import Matrix
from math import radians
import logging
from typing import List, Optional, Any, Dict, cast
import re
from pcbooth.modules.bounding_box import Bounds
from treelib import Tree  # type: ignore

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
    if bpy.context.active_object is not None and bpy.context.active_object.mode == "EDIT":
        bpy.ops.object.mode_set(mode="OBJECT")

    if not bpy.data.objects:
        raise RuntimeError("No objects found in the .blend file, aborting.")


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
    object.location = (0.0, 0.0, 0.0)
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
    rotation = radians(int(display_rot))
    object.rotation_euler = [0, 0, rotation]
    apply_all_transforms(object)


def update_depsgraph() -> None:
    """Update Blender dependency graph tree. Needed to refresh translation matrix of an object."""
    bpy.context.view_layer.update()  # type: ignore


def select_all(parent_obj: bpy.types.Object) -> List[bpy.types.Object]:
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


def get_library_instances(obj: bpy.types.Object) -> List[bpy.types.Object]:
    """Get instances of objects belonging to specified object using depsgraph as a lookup."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    return [
        cast(bpy.types.Object, dg_obj.object.original)
        for dg_obj in depsgraph.object_instances
        if dg_obj.parent and dg_obj.parent.original == obj
    ]


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


def link_obj_to_collection(obj: bpy.types.Object, target_coll: bpy.types.Collection) -> None:
    """Loop through all collections the obj is linked to and unlink it from there, then link to target collection."""
    for coll in obj.users_collection:  # type: ignore
        coll.objects.unlink(obj)
    target_coll.objects.link(obj)


def get_collection(name: str, parent: Optional[bpy.types.Collection] = None) -> bpy.types.Collection:
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


def add_empty(
    name: str,
    target_coll: Optional[bpy.types.Collection] = None,
    children: List[bpy.types.Object] = [],
    origin_source: List[bpy.types.Object] = [],
) -> bpy.types.Object:
    """
    Add empty object to the scene. If no target collection is specified, it will be linked to root scene collection.
    Objects from `children` list are parented to the created empty.
    Empty object is placed in the center point of `origin_source` objects bounding box ([0,0,0] point is used if both `origin_source` and `children` are empty).
    """
    object = bpy.data.objects.new(name, None)
    if target_coll:
        link_obj_to_collection(object, target_coll)
    else:
        bpy.context.scene.collection.objects.link(object)

    if children:
        if not origin_source:
            origin_source = children
        with Bounds(children) as target:
            set_origin(target.bounds)
            object.location = target.bounds.location.copy()
        parent_list_to_object(children, object)
    return object


def set_origin(object: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    object.select_set(True)
    bpy.context.view_layer.objects.active = object
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    bpy.ops.object.select_all(action="DESELECT")


def get_linked() -> List[bpy.types.Object]:
    """
    Get all linked objects in the scene. Returns list of Object of collection instance types.
    Those objects can be used as parent of the linked collections for translations or defining
    visibility
    """
    return [object for object in bpy.data.objects if object.instance_type == "COLLECTION"]


def get_designator(object: bpy.types.Object) -> str:
    """
    Extract designator part out of object's name using regex.
    Expects <DES><idx>:<component value> string as object name.
    """
    regexp = r"^([A-Z]+\d+)\:*"
    result = re.search(regexp, object.name)
    if result:
        return result.group(1)
    return ""


def print_hierarchy() -> None:
    """
    Generate object and collection hierarchy output string of the currently opened .blend file and print it to console.
    """
    obj_map = {"CAMERA": "📽", "LIGHT": "☀︎", "MESH": "▽", "EMPTY": "⸭"}
    col = "🗀"
    link = " [\x1b[3mlinked\x1b[0m]"

    def _get_struct(item: bpy.types.Collection) -> Dict[str, Any]:
        """Get Blender outliner hierarchy as a dict."""
        if isinstance(item, bpy.types.Collection):
            struct: Dict[str, Any] = {}
            collection_key = f"{col}  {item.name}"
            struct[collection_key] = {}

            for obj in item.objects:
                obj_key = f"{obj_map.get(obj.type, '?')}  {obj.name}{link if obj.instance_type == 'COLLECTION' else ''}"
                struct[collection_key][obj_key] = None

            for child_collection in item.children:
                struct[collection_key].update(_get_struct(child_collection))

            return struct
        return {}

    def _make_tree(tree: Tree, data: Dict[str, Any], parent: Optional[str] = None) -> None:
        """Create treelib Tree."""
        for key, value in data.items():
            tree.create_node(key, key, parent=parent)
            if isinstance(value, dict):
                _make_tree(tree, value, key)

    logger.info(f"Legend: {obj_map}")
    root_col = bpy.context.view_layer.layer_collection.collection
    struct = _get_struct(root_col)
    tree = Tree()
    _make_tree(tree, struct)
    logger.info("\n" + str(tree))


def anim_to_deltas(obj: bpy.types.Object) -> None:
    """Transform objects LocRotScale animations to delta animations."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.anim_transforms_to_deltas()
    obj.select_set(False)
