"""Bounding box calculation module"""

from typing import List, Tuple
from mathutils import Vector
import bpy
import logging

import pcbooth.modules.custom_utilities as cu

logger = logging.getLogger(__name__)


def generate_bbox(objects: List[bpy.types.Object]) -> bpy.types.Object:
    """
    Generate bounding box EMPTY object using both locally added and linked objects.
    """
    logger.info("Generating bounding box for loaded model.")
    vertices = []
    objects_list = [obj.name for obj in objects]

    for obj in bpy.data.objects:
        # skip all LIGHT and CAMERA objects
        # TODO: this appears in multiple places, maybe lights and cameras should be
        # skipped at the beginning, when objects list is created?
        if obj.type == "LIGHT":
            logger.debug(f"{obj.name} skipped (type='LIGHT')")
            continue
        if obj.type == "CAMERA":
            logger.debug(f"{obj.name} skipped (type='CAMERA')")
            continue
        # if object comes from linked library, use the original library as source of geometry,
        # apply transforms from the source object then from the linked library
        # there's no need to have the collection named the same as the file
        # there's no need to apply transforms in the source file
        if obj.library:
            if lib_obj := cu.get_root_object(obj):
                logger.debug(f"{obj.name} is linked object from {obj.library.name} lib")
                bbox_obj = [
                    obj.matrix_world @ Vector(corner) for corner in obj.bound_box
                ]
                bbox_lib = [lib_obj.matrix_world @ corner for corner in bbox_obj]
                vertices.extend(bbox_lib)
            else:
                continue
        elif obj.name in objects_list and obj.instance_type == "NONE":
            logger.debug(f"{obj.name} is a local object")
            bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            vertices.extend(bbox)

    if not vertices:
        raise RuntimeError(f"No bounding box vertices found")

    bbox_verts = calculate_bbox(vertices)
    obj = generate_mesh(bbox_verts)
    logger.debug(f"Generated bounding box object {obj} ({bbox_verts})")
    return obj


def generate_mesh(vertices: List[Vector]) -> bpy.types.Object:
    """Generate mesh from vertices, edges and faces lists"""
    mesh = bpy.data.meshes.new("BBOX")
    mesh.from_pydata(vertices, [], [])
    mesh.update()
    obj = bpy.data.objects.new("BBOX", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def calculate_bbox(vector: List[Vector]) -> List[Tuple[int, int, int]]:
    """Calculate bounding box in form of list of tuples from provided list of points"""
    # Initialize min and max values with the coordinates of the first point
    min_x, min_y, min_z = max_x, max_y, max_z = vector[0].x, vector[0].y, vector[0].z

    # Update min and max values by iterating through the list of points
    for point in vector:
        min_x = min(min_x, point.x)
        min_y = min(min_y, point.y)
        min_z = min(min_z, point.z)
        max_x = max(max_x, point.x)
        max_y = max(max_y, point.y)
        max_z = max(max_z, point.z)
    # Construct the 8-point bounding box coordinates
    bounding_box = [
        (min_x, min_y, min_z),
        (min_x, max_y, min_z),
        (max_x, max_y, min_z),
        (max_x, min_y, min_z),
        (min_x, min_y, max_z),
        (min_x, max_y, max_z),
        (max_x, max_y, max_z),
        (max_x, min_y, max_z),
    ]
    return bounding_box
