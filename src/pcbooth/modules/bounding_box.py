"""Bounding box calculation module."""

import bpy
from typing import List, Tuple, Self, Type
from mathutils import Vector
import logging
import pcbooth.modules.custom_utilities as cu
from types import TracebackType

logger = logging.getLogger(__name__)

BOUNDS_NAME = "_bounds"


class BoundsVerticesCreationError(Exception):
    """Bounds generation error."""

    pass


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
        """Initialize bounds context manager and create bounds empty object."""

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
        """Remove bounds data from scene."""
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
    objects_list = [obj for obj in objects if not obj.is_library_indirect]
    for obj in objects_list:
        _bbox = []
        if instances := cu.get_library_instances(obj):
            _bbox = next((_get_translations_from_link(i, obj) for i in instances), [])
        else:
            _bbox = _get_translations_local(obj)
        vertices.extend(_bbox)

    if not vertices:
        raise BoundsVerticesCreationError(f"No vertices found in children objects, can't generate Bounds.")

    return vertices


def _get_translations_from_link(obj: bpy.types.Object, lib_obj: bpy.types.Object) -> List[Vector]:
    """
    Get matrix world translations from the local object and apply it to object's bounding box vertices,
    then apply translations from the linked source.
    """
    bbox_obj_verts = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]  # type: ignore
    bbox_lib_verts = [lib_obj.matrix_world @ corner for corner in bbox_obj_verts]
    return bbox_lib_verts


def _get_translations_local(obj: bpy.types.Object) -> List[Vector]:
    """Get matrix world translations from the local object and apply it to object's bounding box vertices."""
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]  # type: ignore


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
    """Generate EMPTY object out of cloud of vertices using both locally added and linked objects."""
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
