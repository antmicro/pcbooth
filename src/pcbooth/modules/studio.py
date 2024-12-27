"""
Studio generation module. Handles loading rendered Blender model and configures itself according to read data. 
Adds cameras, lights and backgrounds.
"""

import bpy
from math import radians
from typing import List, Dict
from mathutils import Matrix
import logging

import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.camera import Camera
from pcbooth.modules.background import Background
from pcbooth.modules.light import Light, disable_emission_nodes
from pcbooth.modules.renderer import init_render_settings, set_default_compositing


logger = logging.getLogger(__name__)


class Studio:
    presets = {
        "TOP": (radians(0), radians(0), radians(0)),
        "BOTTOM": (radians(0), radians(180), radians(0)),
        "REAR": (radians(0), radians(0), radians(180)),
    }

    def __init__(self, pcb_blend_path: str):
        cu.open_blendfile(pcb_blend_path)
        init_render_settings()
        set_default_compositing()
        self.collection = cu.get_collection("Studio")

        self.is_pcb: bool = False
        self.is_collection: bool = False
        self.is_object: bool = False
        self.rendered_obj: bpy.types.Object = None  # object to align camera to
        self.top_parent: bpy.types.Object = None  # object to apply rotation
        self.display_rot: int = 0
        self.top_components: List[bpy.types.Object] = []
        self.bottom_components: List[bpy.types.Object] = []
        self.cameras: List[Camera] = []
        self.backgrounds: List[Background] = []
        self.lights: List[Light] = []
        self.positions: List[str]

        self._configure_model_data()
        self._configure_position()

        self._add_cameras()
        self._add_lights()
        self._add_backgrounds()
        self._apply_effects()

    def _add_cameras(self):
        Camera.add_collection()

        cameras = get_keys(config.blendcfg["CAMERAS"], skipped=["ORTHO_TYPE", "CUSTOM"])
        positions = get_keys(
            config.blendcfg["OBJECT"], skipped=["AUTO_ROTATE", "RENDERED_OBJECT"]
        )

        for camera_name in cameras:
            Camera(camera_name, Camera.presets[camera_name])
        if config.blendcfg["CAMERAS"]["CUSTOM"]:
            if camera_custom := bpy.data.objects.get("camera_custom"):
                Camera(camera=camera_custom)
            else:
                logger.warning(
                    f"[CAMERAS][CUSTOM] enabled but no 'camera_custom' predefined object found in Blender file."
                )

        for camera in Camera.objects:
            for position in positions:
                self.change_position(position)
                camera.align(self.rendered_obj)
                camera.save_position(position)
                camera.save_focus(position)

        logger.info(
            f"Added {len(Camera.objects)} cameras to Studio: {[cam.object.name for cam in Camera.objects]}"
        )
        self.cameras = Camera.objects
        self.positions = positions
        self.change_position("TOP")

    def _add_backgrounds(self):
        Background.add_collection()

        for bg_name in config.blendcfg["STUDIO_EFFECTS"]["BACKGROUND"]:
            Background(bg_name)

        Background.update_position(self.top_parent)
        logger.info(
            f"Added {len(Background.objects)} backgrounds to Studio: {[bg.object.name for bg in Background.objects]}"
        )
        self.backgrounds = Background.objects

    def _add_lights(self):
        Light.add_collection()
        Light.bind_to_object(self.top_parent)

        for light_name in Light.presets:
            Light(light_name, *Light.presets[light_name])

        logger.info(
            f"Added {len(Light.objects)} lights to Studio: {[light.object.name for light in Light.objects]}"
        )
        self.lights = Light.objects

    def _apply_effects(self):
        """Enable or disable additional studio effects"""
        if not config.blendcfg["STUDIO_EFFECTS"]["LED_ON"]:
            disable_emission_nodes()

    def _configure_model_data(self):
        """Assign configurational attributes' values based on loaded model contents."""
        logger.info("Configuring studio...")

        obj_type, rendered_obj_name = "", ""
        if config.blendcfg["OBJECT"]["RENDERED_OBJECT"]:
            obj_type = config.blendcfg["OBJECT"]["RENDERED_OBJECT"][0]
            rendered_obj_name = config.blendcfg["OBJECT"]["RENDERED_OBJECT"][1]

        # single object picked using RENDERED_OBJECT setting
        if obj_type == "Object":
            logger.info(f"Rendering from object: {rendered_obj_name}")
            self._configure_as_singleobject(rendered_obj_name)
            return

        # single collection picked using RENDERED_OBJECT setting
        if obj_type == "Collection":
            logger.info(f"Rendering from collection: {rendered_obj_name}")
            self._configure_as_collection(rendered_obj_name)
            return

        # PCB generated using gerber2blend
        if bpy.data.collections.get("Board") and bpy.data.objects.get(config.PCB_name):
            logger.info("PCB type model was recognized.")
            self._configure_as_PCB()
            return

        # Unknown type model
        # if there's only one object it gets treated as single object
        if len(bpy.data.objects) == 1:
            rendered_obj_name = bpy.data.objects[0].name
            logger.info(f"Rendering from object: {rendered_obj_name}")
            self._configure_as_singleobject(rendered_obj_name)
        else:
            logger.info("Unknown type model was recognized.")
            self._configure_as_unknown()

    def _configure_as_PCB(self):
        self.is_pcb = True
        self.top_parent = bpy.data.objects.get(config.PCB_name, "")
        if not self.top_parent:
            raise RuntimeError(
                f"{config.PCB_name} object could not be found in Blender model data."
            )
        self.rendered_obj = self.top_parent
        self.components = cu.select_all(self.top_parent)
        self._get_top_bottom_components()

    def _configure_as_collection(self, collection_name):
        self.is_collection = True
        rendered_col = bpy.data.collections.get(collection_name, "")
        if not rendered_col:
            raise RuntimeError(
                f"{collection_name} collection could not be found in Blender model data."
            )
        scene_components = [object for object in bpy.data.objects]
        rendered_components = [object for object in rendered_col.objects]
        self._get_top_bottom_components(rendered_components)
        self.top_parent = cu.add_empty("_parent")
        self.rendered_obj = cu.add_empty("_rendered_parent")
        cu.parent_list_to_object(rendered_components, self.rendered_obj)
        cu.parent_list_to_object(scene_components, self.top_parent)

    def _configure_as_singleobject(self, object_name):
        self.is_object = True
        self.rendered_obj = bpy.data.objects.get(object_name, "")
        if not self.rendered_obj:
            raise RuntimeError(
                f"{object_name} object could not be found in Blender model data."
            )
        self._get_top_bottom_components([self.rendered_obj])
        self.top_parent = cu.get_top_parent(self.rendered_obj)
        cu.set_origin(self.rendered_obj)  # needed to correctly calculate focus

    def _configure_as_unknown(self):
        self.top_parent = cu.add_empty("_parent")
        self.rendered_obj = self.top_parent
        components = [object for object in bpy.data.objects]
        self._get_top_bottom_components(components)
        cu.parent_list_to_object(components, self.top_parent)

    def _configure_position(self):
        """
        Adjust model position before render and assign values to positions dict.
        When selected object is a child, rotates and moves top parent.
        """
        object = cu.get_top_parent(self.rendered_obj)

        if config.blendcfg["OBJECT"]["AUTO_ROTATE"]:
            if self.is_pcb:
                cu.rotate_horizontally(object)

            if self.is_object and len(self.top_components) == 1:
                self.display_rot = self.rendered_obj.get("DISPLAY_ROT", 0)
                cu.apply_display_rot(object, self.display_rot)

        if self.is_object and len(self.top_components) == 1:
            cu.center_on_scene(object)

    def _get_top_bottom_components(self, objects: List[bpy.types.Object] = []) -> None:
        """
        Load top and bottom component lists using char stored in 'PCB_Side' custom property (PCB model type only).
        This custom property is saved in objects when they're imported using picknblend tool.
        If `enable_all` argument is set to true, all available components passed to function will be added to both of the lists.
        """
        top_comps = []
        bot_comps = []
        if self.is_pcb:
            components = bpy.data.collections.get("Components")
            if not components:
                return
            for comp in components.objects:
                if "PCB_Side" not in comp.keys():
                    continue
                if comp["PCB_Side"] == "T":
                    top_comps.append(comp)
                elif comp["PCB_Side"] == "B":
                    bot_comps.append(comp)
        else:
            top_comps = [obj for obj in objects if not obj.name.startswith("_")]
            bot_comps = top_comps.copy()
        logger.debug(f"Read top components: {top_comps}")
        logger.debug(f"Read bot components: {bot_comps}")
        self.top_components = top_comps
        self.bottom_components = bot_comps

    def change_position(self, key: str):
        """
        Move rendered_object to position saved in dictionary.
        """
        object = cu.get_top_parent(self.rendered_obj)
        object.rotation_euler = self.presets[key]
        logger.debug(f"Moved {self.rendered_obj.name} to '{key}' position")
        cu.update_depsgraph()


def get_keys(cfg: Dict[str, bool], skipped: List[str]) -> List[str]:
    """Retrieve keys from a dictionary that have a `True` value and are not in a specified list of skipped keys."""
    return [key for key, value in cfg.items() if value and key not in skipped]
