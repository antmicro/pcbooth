"""Module handling lights configuration and positioning."""

import bpy
from math import radians
from typing import List, Tuple, Dict, ClassVar, Optional
import logging

from bpy.types import Object

import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.bounding_box import Bounds


logger = logging.getLogger(__name__)


def load_hdri() -> None:
    """Load HDRI environmental texture and setup it's World shader."""

    scene = bpy.context.scene
    nodes = scene.world.node_tree.nodes
    links = scene.world.node_tree.links
    nodes.clear()  # type: ignore

    texture_coordinate = nodes.new(type="ShaderNodeTexCoord")

    mapping = nodes.new(type="ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (radians(-30), radians(0), radians(160))  # type: ignore

    hdri = nodes.new("ShaderNodeTexEnvironment")
    hdri.image = bpy.data.images.load(config.env_texture_path)  # type: ignore

    background = nodes.new(type="ShaderNodeBackground")
    background.inputs["Strength"].default_value = config.blendcfg["SCENE"][  # type: ignore
        "HDRI_INTENSITY"
    ]

    output = nodes.new(type="ShaderNodeOutputWorld")

    links.new(texture_coordinate.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], hdri.inputs["Vector"])
    links.new(hdri.outputs["Color"], background.inputs["Color"])
    links.new(background.outputs["Background"], output.inputs["Surface"])

    logger.info(f"Configured HDRI ({config.env_texture_path})")


def calculate_light_intensity(scale: int, x: float, y: float) -> float:
    """
    Calculate scaled light intensity in relation to rendered object dimensions.
    Uses linear relation between longer x or y dimension of the model.
    Uses 4000W intensity as a base.
    Returns base intensity as constant for models with max(x,y) < 45.
    Otherwise calculates intensity using base and multiplier.
    """
    base = 4000
    max_dim = max(x, y)
    return (260 * max_dim + base) * scale if max_dim > 45 else base * scale


def calculate_z_coordinate(max_z: float, x: float, y: float) -> float:
    """
    Calculate Z coordinate of the light object. Adds model's max Z dimension to calculated base.
    Uses linear relation between longer x or y dimension of the model. Caps base at 70 for
    models with longer edge of above 65.
    """
    base = 70
    max_dim = max(x, y)
    return max_z + base if max_dim > 65 else max_z + 0.289 * max_dim + 22.3


def calculate_light_size(x: float, y: float) -> Tuple[float, float]:
    """
    Calculate light object x and y dimension. Uses linear relation between model's dimensions.
    Assumes longer edge is x.
    """
    max_dim = max(x, y)
    min_dim = min(x, y)

    x_size = 1.05 * max_dim + 34.9
    y_size = 0.275 * min_dim * 19.6
    return (x_size, y_size)


def disable_emission_nodes() -> None:
    """
    Utility function, mute or reduce strength in emission-like shader nodes.
    """
    for material in bpy.data.materials:
        if not material.node_tree:
            continue

        for node in material.node_tree.nodes:
            if node.type == "EMISSION":
                node.mute = True
            if node.type == "BSDF_PRINCIPLED":
                node.inputs[27].default_value = 0  # type: ignore


class Light:
    objects: ClassVar[List["Light"]] = []
    collection: bpy.types.Collection
    presets: Dict[
        str, Tuple[Tuple[float, float, float], tuple[float, float, float], float]
    ] = {}
    obj_y: float = 0.0
    obj_x: float = 0.0

    @classmethod
    def add_collection(cls) -> None:
        """
        Create new Lights collection, configures HDRI.
        """
        studio = cu.get_collection("Studio")
        collection = cu.get_collection("Lights", studio)
        cls.collection = collection
        load_hdri()

    @classmethod
    def get(cls, name: str) -> Optional["Light"]:
        """Get Camera object by name string."""
        for object in cls.objects:
            if object.name == name:
                return object
        logger.warning(f"Light: {name} not found.")
        return None

    @classmethod
    def bind_to_object(cls, object: bpy.types.Object) -> None:
        """
        Bind Light class to rendered object and calculate preset positions.
        This way they can be adjusted proportionally to rendered object size.
        """
        with Bounds(cu.select_all(object)) as target:
            cls.obj_x = target.bounds.dimensions.x
            cls.obj_y = target.bounds.dimensions.y
            z_coord = calculate_z_coordinate(target.max_z, cls.obj_x, cls.obj_y)

        # presets include rotation tuple, location tuple, internal intensity
        cls.presets = {
            "TOP": ((radians(0), radians(0), radians(0)), (0.0, 0.0, z_coord), 1.0),
            "BACK": (
                (radians(-25), radians(0), radians(0)),
                (0.0, cls.obj_y / 2, z_coord),
                0.66,
            ),
        }

    @classmethod
    def update_position(cls, object: bpy.types.Object, restore: bool = False):
        """Update position (Z coordinate) of all added lights in relation to current highest point of rendered object"""
        if restore:
            for lt in cls.objects:
                lt.object.rotation_euler = cls.presets[lt.name][0]
                lt.object.location = cls.presets[lt.name][1]
        else:
            with Bounds(cu.select_all(object)) as target:
                z_coord = calculate_z_coordinate(target.max_z, cls.obj_x, cls.obj_y)
            for lt in cls.objects:
                lt.object.location.z = z_coord
        logger.debug(f"Lights moved to Z: {lt.object.location.z}")
        cu.update_depsgraph()

    def __init__(
        self,
        name: str,
        rotation: Tuple[float, float, float],
        location: Tuple[float, float, float],
        intensity: float,
    ):
        if not Light.collection:
            raise ValueError(
                f"Lights collection is not added, call add_collection class method before creating an instance."
            )
        if not Light.presets:
            raise ValueError(
                f"Lights presets are not calculated, call bind_to_object class method before creating an instance."
            )

        self.object: bpy.types.Object = self._add(name, rotation, location, intensity)
        self.name = name

    def _add(
        self,
        name: str,
        rotation: Tuple[float, float, float],
        location: Tuple[float, float, float],
        intensity: float,
    ) -> bpy.types.Object:
        """
        Create light object.
        """
        light_name = "light_" + name.lower()
        light = bpy.data.lights.new(light_name, type="AREA")
        light.spread = radians(140)  # type: ignore
        light.color = cu.hex_to_rgb(config.blendcfg["SCENE"]["LIGHTS_COLOR"])
        light.shape = "RECTANGLE"  # type: ignore

        config_intensity = config.blendcfg["SCENE"]["LIGHTS_INTENSITY"] * intensity
        light.energy = calculate_light_intensity(  # type: ignore
            config_intensity, Light.obj_x, Light.obj_y
        )

        light_size = calculate_light_size(Light.obj_x, Light.obj_y)
        light.size = light_size[0]  # type: ignore
        light.size_y = light_size[1]  # type: ignore

        object = bpy.data.objects.new(light_name, light)
        object.rotation_euler = rotation
        object.location = location
        cu.link_obj_to_collection(object, Light.collection)

        cu.update_depsgraph()
        logger.debug(f"Added light object at: \n{object.matrix_world}")
        Light.objects.append(self)

        return object
