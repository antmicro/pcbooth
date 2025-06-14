"""Module handling lights configuration and positioning."""

import bpy
from math import radians
from typing import List, Tuple, Dict, ClassVar, Optional
import logging

import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.bounding_box import Bounds


logger = logging.getLogger(__name__)


def load_hdri() -> None:
    """Load HDRI environmental texture and setup it's World shader."""

    scene = bpy.context.scene
    if not scene.world:
        scene.world = bpy.data.worlds.new(name="World")
    scene.world.use_nodes = True
    nodes = scene.world.node_tree.nodes
    links = scene.world.node_tree.links
    nodes.clear()  # type: ignore

    texture_coordinate = nodes.new(type="ShaderNodeTexCoord")

    mapping = nodes.new(type="ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (radians(-30), radians(0), radians(160))  # type: ignore

    hdri = nodes.new("ShaderNodeTexEnvironment")
    hdri.image = bpy.data.images.load(config.env_texture_path)  # type: ignore

    background = nodes.new(type="ShaderNodeBackground")
    background.inputs["Strength"].default_value = config.blendcfg["SCENE"]["HDRI_INTENSITY"]  # type: ignore

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
    presets: Dict[str, Tuple[Tuple[float, float, float], tuple[float, float, float], float]] = {
        "TOP": ((radians(0), radians(0), radians(0)), (0.0, 0.0, 0.0), 1.0),
        "BACK": (
            (radians(-25), radians(0), radians(0)),
            (0.0, 0.5, 0.0),
            0.66,
        ),
    }

    @classmethod
    def add_collection(cls) -> None:
        """Create new Lights collection, configures HDRI."""
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
    def update(cls, obj: bpy.types.Object) -> None:
        """Update position and power of all lights based on highest point of rendered object and its dimensions."""
        with Bounds(cu.select_all(obj)) as target:
            cu.set_origin(target.bounds)
            obj_x = target.bounds.dimensions.x
            obj_y = target.bounds.dimensions.y
            z_coord = calculate_z_coordinate(target.max_z, obj_x, obj_y)
            offset = (target.bounds.location.x, target.bounds.location.y, z_coord)
            for lt in cls.objects:
                pos_preset = cls.presets[lt.name][1]
                intensity_preset = cls.presets[lt.name][2]
                dimensions = target.bounds.dimensions.to_tuple()
                new_pos = tuple(pos * dim for pos, dim in zip(pos_preset, dimensions, strict=True))
                lt.object.location = tuple(pos + offset for pos, offset in zip(new_pos, offset, strict=True))
                logger.debug(f"Light `{lt.name}` moved to: {lt.object.location}")

                config_intensity = config.blendcfg["SCENE"]["LIGHTS_INTENSITY"] * intensity_preset
                lt.object.data.energy = calculate_light_intensity(config_intensity, obj_x, obj_y)  # type: ignore

                light_size = calculate_light_size(obj_x, obj_y)
                lt.object.data.size = light_size[0]  # type: ignore
                lt.object.data.size_y = light_size[1]  # type: ignore
        cu.update_depsgraph()

    @classmethod
    def keyframe_all(cls, frame: int) -> None:
        """Keyframe all Light objects."""
        for lt in cls.objects:
            lt.add_keyframe(frame)

    def add_keyframe(self, frame: int) -> None:
        """Keyframe Light settings."""
        self.object.keyframe_insert(data_path="rotation_euler", frame=frame)
        self.object.keyframe_insert(data_path="location", frame=frame)
        self.object.data.keyframe_insert(data_path="energy", frame=frame)  # type: ignore
        self.object.data.keyframe_insert(data_path="size", frame=frame)  # type: ignore
        self.object.data.keyframe_insert(data_path="size_y", frame=frame)  # type: ignore

    def __init__(
        self,
        name: str,
        rotation: Tuple[float, float, float],
        location: Tuple[float, float, float],
        intensity: float,
    ):
        if not Light.collection:
            Light.add_collection()

        self.object: bpy.types.Object = self._add(name, rotation, location, intensity)
        self.name = name

    def _add(
        self,
        name: str,
        rotation: Tuple[float, float, float],
        location: Tuple[float, float, float],
        intensity: float,
    ) -> bpy.types.Object:
        """Create light object."""
        light_name = "light_" + name.lower()
        light = bpy.data.lights.new(light_name, type="AREA")
        light.spread = radians(140)  # type: ignore
        light.color = cu.hex_to_rgb(config.blendcfg["SCENE"]["LIGHTS_COLOR"])
        light.shape = "RECTANGLE"  # type: ignore

        object = bpy.data.objects.new(light_name, light)
        object.rotation_euler = rotation
        object.location = location
        cu.link_obj_to_collection(object, Light.collection)

        cu.update_depsgraph()
        logger.debug(f"Added light object at: \n{object.matrix_world}")
        Light.objects.append(self)

        return object
