"""
Studio generation module. Handles loading rendered Blender model and configures itself according to read data. 
Adds cameras, lights and backgrounds.
"""

import bpy
import pcbooth.modules.config as config
from mathutils import Vector, Matrix
from math import radians
import logging
import pcbooth.modules.custom_utilities as cu
import pcbooth.modules.bounding_box as bb
from pcbooth.modules.camera import Camera
from typing import List, Dict

logger = logging.getLogger(__name__)


class Studio:
    presets = {
        "TOP": (radians(0), radians(0), radians(0)),
        "BOTTOM": (radians(0), radians(180), radians(0)),
        "REAR": (radians(0), radians(0), radians(180)),
    }

    def __init__(self, pcb_blend_path: str):
        cu.open_blendfile(pcb_blend_path)
        self.collection = cu.get_collection("Studio")

        self.is_pcb: bool = False
        self.is_collection: bool = False
        self.is_object: bool = False
        self.is_unknown: bool = True
        self.rendered_obj: bpy.types.Object = None
        self.display_rot: int = 0
        self.top_components: List[bpy.types.Object] = []
        self.bottom_components: List[bpy.types.Object] = []
        self.positions: Dict[str, mathutils.Matrix] = {}

        self._configure_model_data()
        self._configure_position()

        self._add_cameras()

        # TODO: add background

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

        logger.info(
            f"Added {len(Camera.objects)} cameras to Studio: {[cam.object.name for cam in Camera.objects]}"
        )

    def _configure_model_data(self):
        """Assign configurational attributes' values based on loaded model contents."""
        obj_type, rendered_obj_name = "", ""
        if config.blendcfg["OBJECT"]["RENDERED_OBJECT"]:
            obj_type = config.blendcfg["OBJECT"]["RENDERED_OBJECT"][0]
            rendered_obj_name = config.blendcfg["OBJECT"]["RENDERED_OBJECT"][1]

        # single custom object picked using RENDERED_OBJECT setting
        if obj_type == "Object":
            logger.info(f"Rendering from object: {rendered_obj_name}")
            self._configure_as_singleobject(rendered_obj_name)
            return

        # single collection picked using RENDERED_OBJECT setting
        # will work as Assembly collection before
        if obj_type == "Collection":
            logger.info(f"Rendering from collection: {rendered_obj_name}")
            self._configure_as_collection(rendered_obj_name)
            return

        # PCB generated using gerber2blend
        # can be without components
        if bpy.data.collections.get("Board") and bpy.data.objects.get(config.PCB_name):
            logger.info("PCB type model was recognized.")
            self._configure_as_PCB(config.PCB_name)
            return

        # Unknown type model
        # check if there's only one object
        # if there's more, treat it as collection
        if len(bpy.data.objects) == 1:
            rendered_obj_name = bpy.data.objects[0].name
            logger.info(f"Rendering from object: {rendered_obj_name}")
            self._configure_as_singleobject(rendered_obj_name, adjust_pos=True)
        else:
            logger.info("Unknown type model was recognized.")
            self._configure_as_unknown()

    def _configure_as_PCB(self, object_name):
        self.rendered_obj = bpy.data.objects.get(object_name, "")
        if not self.rendered_obj:
            raise RuntimeError(
                f"{object_name} object could not be found in Blender model data."
            )
        self.top_components, self.bottom_components = (
            cu.get_top_bottom_component_lists()
        )
        self.is_unknown = False
        self.is_pcb = True
        components_col = bpy.data.collections.get("Components")
        components = [object for object in components_col.objects]
        bbox_obj = bb.generate_bbox(components + [self.rendered_obj])
        cu.parent_list_to_object([bbox_obj], self.rendered_obj)

    def _configure_as_collection(self, collection_name):
        rendered_col = bpy.data.collections.get(collection_name, "")
        if not rendered_col:
            raise RuntimeError(
                f"{collection_name} collection could not be found in Blender model data."
            )
        components = [object for object in rendered_col.objects]
        self.rendered_obj = bb.generate_bbox(components)
        self.top_components, self.bottom_components = cu.get_top_bottom_component_lists(
            components, enable_all=True
        )
        self.is_unknown = False
        self.is_collection = True
        cu.link_obj_to_collection(self.rendered_obj, rendered_col)
        cu.parent_list_to_object(components, self.rendered_obj)

    def _configure_as_singleobject(self, object_name):
        self.rendered_obj = bpy.data.objects.get(object_name, "")
        if not self.rendered_obj:
            raise RuntimeError(
                f"{object_name} object could not be found in Blender model data."
            )
        self.is_unknown = False
        self.is_object = True
        self.display_rot = self.rendered_obj.get("DISPLAY_ROT", 0)

    def _configure_as_unknown(self):
        components = [object for object in bpy.data.objects]
        self.rendered_obj = bb.generate_bbox(components)
        self.top_components, self.bottom_components = cu.get_top_bottom_component_lists(
            components, enable_all=True
        )
        cu.parent_list_to_object(components, self.rendered_obj)

    def _configure_position(self):
        """
        Adjust model position before render and assign values to positions dict.
        When selected object is a child, rotates and moves top parent.
        """
        object = cu.get_top_parent(self.rendered_obj)

        if config.blendcfg["OBJECT"]["AUTO_ROTATE"]:
            if self.is_pcb:
                cu.rotate_horizontally(object)

            if self.is_object:
                cu.apply_display_rot(object, self.display_rot)

        if self.is_object:
            cu.center_on_scene(object)

    def change_position(self, key: str):
        """
        Move rendered_object to position saved in dictionary.
        """
        object = cu.get_top_parent(self.rendered_obj)
        object.rotation_euler = self.presets[key]
        logger.debug(f"Moved {self.rendered_obj.name} to '{key}' position")


def get_keys(cfg: Dict[str, bool], skipped: List[str]) -> List[str]:
    """Retrieve keys from a dictionary that have a `True` value and are not in a specified list of skipped keys."""
    return [key for key, value in cfg.items() if value and key not in skipped]
