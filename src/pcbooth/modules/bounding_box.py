"""Bounding box calculation module."""

import bpy
from typing import List, Tuple, Self, Type
from mathutils import Vector
import logging
import pcbooth.modules.custom_utilities as cu
from types import TracebackType

logger = logging.getLogger(__name__)

BOUNDS_NAME = "_bounds"


class Bounds:
    """
    Context manager class.
    Generate single bounds object consisting of bounding boxes of objects passed as a list.
    This object can be then used to determine entire list's total dimensions. Bounds object
    gets removed on context mangers' exit.
    Attributes:
        objects :
            list of objects used to create an instance of Bounds class
        bounds :
            Blender bounds object made out of bounding box vertices of objects from objects list
        min_z :
            lowest vertex Z value
        max_z :
            highest vertex Z value
    """

    def __init__(self, objects: List[bpy.types.Object]) -> None:
        """
        Initialize bounds context manager and create bounds empty object.
        """
        self.objects: List[bpy.types.Object] = objects
        self.bounds: bpy.types.Object = generate_bounds(self.objects)
        self.min_z: float = self._get_min_z()
        self.max_z: float = self._get_max_z()

    def __enter__(self) -> Self:
        """Return Bounds object."""
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        """
        Remove bounds data from scene.
        """
        self.clear()

    def _get_min_z(self) -> float:
        """Get lowest Z coordinate of all bounding box vertices coordinates of an object"""
        current_vertices = [Vector(v[:]) @ self.bounds.matrix_world for v in self.bounds.bound_box]  # type: ignore
        return min([v.z for v in current_vertices])

    def _get_max_z(self) -> float:
        """Get highest Z coordinate of all bounding box vertices coordinates of an object"""
        current_vertices = [Vector(v[:]) @ self.bounds.matrix_world for v in self.bounds.bound_box]  # type: ignore
        return max([v.z for v in current_vertices])

    def clear(self) -> None:
        """Clear bounds object data."""
        bpy.data.meshes.remove(self.bounds.data)  # type: ignore


def get_vertices(
    objects: List[bpy.types.Object],
) -> List[Vector]:
    """Get list of all vertices of objects passed as a list."""
    vertices = []
    objects_list = [obj.name for obj in objects]

    for obj in bpy.data.objects:
        # skip all LIGHT, CAMERA and BACKGROUND objects
        if obj.type == "LIGHT":
            continue
        if obj.type == "CAMERA":
            continue
        if obj.library:
            if "templates/backgrounds" in obj.library.filepath:
                continue
        # if object comes from linked library, use the original library as source of geometry,
        # apply transforms from the source object then from the linked library
        # there's no need to have the collection named the same as the file
        # there's no need to apply transforms in the source file
        if obj.library:
            if lib_obj := cu.get_root_object(obj):
                bbox_obj = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]  # type: ignore
                bbox_lib = [lib_obj.matrix_world @ corner for corner in bbox_obj]
                vertices.extend(bbox_lib)
            else:
                continue
        elif obj.name in objects_list and obj.instance_type == "NONE":
            bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]  # type: ignore
            vertices.extend(bbox)
    if not vertices:
        raise RuntimeError(f"No rendered object vertices found")
    return vertices


def generate_bbox(objects: List[bpy.types.Object]) -> bpy.types.Object:
    """
    Generate bounding box EMPTY object using both locally added and linked objects.
    """
    vertices = get_vertices(objects)
    bbox_verts = calculate_bbox(vertices)
    obj = generate_mesh(bbox_verts)

    logger.debug(f"Generated bounding box object {obj} ({bbox_verts})")
    return obj


def generate_bounds(objects: List[bpy.types.Object]) -> bpy.types.Object:
    """
    Generate EMPTY object out of cloud of vertices using both locally added and linked objects.
    """
    vertices = get_vertices(objects)
    obj = generate_mesh(vertices)

    logger.debug(f"Generated bounds object {obj}")
    return obj


def generate_mesh(vertices: List[Tuple[float, float, float]] | List[Vector]) -> bpy.types.Object:
    """Generate mesh from vertices, edges and faces lists"""
    mesh = bpy.data.meshes.new(BOUNDS_NAME)
    mesh.from_pydata(vertices, [], [])
    mesh.update()
    obj = bpy.data.objects.new(BOUNDS_NAME, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def calculate_bbox(
    vector: List[Vector],
) -> List[Tuple[float, float, float]]:
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
