"""Module handling lights configuration and positioning."""

import bpy
from math import radians
from typing import List, Tuple, Dict, ClassVar, Self
import logging

import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.bounding_box import Bounds


logger = logging.getLogger(__name__)


def load_hdri() -> None:
    """Load HDRI environmental texture and setup it's World shader."""

    scene = bpy.context.scene
    nodes = scene.world.node_tree.nodes
    links = scene.world.node_tree.links
    nodes.clear()

    texture_coordinate = nodes.new(type="ShaderNodeTexCoord")

    mapping = nodes.new(type="ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (radians(-30), radians(0), radians(90))

    hdri = nodes.new("ShaderNodeTexEnvironment")
    hdri.image = bpy.data.images.load(config.env_texture_path)

    background = nodes.new(type="ShaderNodeBackground")
    background.inputs["Strength"].default_value = config.blendcfg["STUDIO_EFFECTS"][
        "ENVTEXTURE_INTENSITY"
    ]

    output = nodes.new(type="ShaderNodeOutputWorld")

    links.new(texture_coordinate.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], hdri.inputs["Vector"])
    links.new(hdri.outputs["Color"], background.inputs["Color"])
    links.new(background.outputs["Background"], output.inputs["Surface"])

    logger.info(f"Configured HDRI ({config.env_texture_path})")


def scale_light_intensity(intensity: int, x: float, y: float) -> float:
    """Calculate scaled light intensity in relation to rendered object dimensions."""
    ratio = max(x / 120, y / 60, 1)
    return intensity * ratio**1.2


def calculate_z_coordinate(max_z: float, x: float, y: float) -> float:
    base_z = 58
    ratio = max(x / 120, y / 60)
    if ratio < 1:
        return max_z + ratio * base_z
    return max_z + base_z


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
                node.inputs[27].default_value = 0


class Light:
    objects: ClassVar[List["Light"]] = []
    collection: bpy.types.Collection = None
    presets: Dict[str, Tuple] = {}
    obj_y: float = 0.0
    obj_x: float = 0.0

    @classmethod
    def add_collection(cls):
        """
        Create new Lights collection, configures HDRI.

        """
        studio = cu.get_collection("Studio")
        collection = cu.get_collection("Lights", studio)
        cls.collection = collection
        load_hdri()

    @classmethod
    def get(cls, name: str) -> Self | None:
        """Get Camera object by name string."""
        for object in cls.objects:
            if object.name == name:
                return object
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
            "TOP": ((radians(0), radians(0), radians(0)), (0, 0, z_coord), 1),
            "BACK": (
                (radians(-25), radians(0), radians(0)),
                (0, cls.obj_y / 2, z_coord),
                0.66,
            ),
        }

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

    def _add(
        self,
        name: str,
        rotation: Tuple[float, float, float],
        location: Tuple[float, float, float],
        intensity: float,
    ):
        """
        Create light object.
        """
        light_name = "light_" + name.lower()
        light = bpy.data.lights.new(light_name, type="AREA")
        light.spread = radians(140)
        light.color = cu.hex_to_rgb(config.blendcfg["STUDIO_EFFECTS"]["LIGHTS_COLOR"])
        light.shape = "RECTANGLE"

        config_intensity = (
            config.blendcfg["STUDIO_EFFECTS"]["LIGHTS_INTENSITY"] * intensity
        )
        light.energy = scale_light_intensity(config_intensity, Light.obj_x, Light.obj_y)

        margin = max(Light.obj_x, Light.obj_y) * 0.4
        light.size = Light.obj_x + margin
        light.size_y = Light.obj_y + margin

        object = bpy.data.objects.new(light_name, light)
        object.rotation_euler = rotation
        object.location = location
        cu.link_obj_to_collection(object, Light.collection)

        cu.update_depsgraph()
        logger.debug(f"Added light object at: \n{object.matrix_world}")
        Light.objects.append(self)
        return object

    # TODO: add some kind of update position method to be used when animating rotations of rendered object
