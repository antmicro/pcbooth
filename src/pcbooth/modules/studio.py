"""
Studio generation module. Handles loading rendered Blender model and configures itself according to read data.
Adds cameras, lights and backgrounds.
"""

import bpy
from math import radians
from typing import List, Dict, Tuple
import logging

import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.camera import Camera
from pcbooth.modules.background import Background
from pcbooth.modules.bounding_box import Bounds
from pcbooth.modules.light import Light, disable_emission_nodes
from pcbooth.modules.renderer import init_render_settings, set_default_compositing


logger = logging.getLogger(__name__)


class Studio:
    presets = {
        "TOP": (radians(0), radians(0), radians(0)),
        "BOTTOM": (radians(0), radians(180), radians(0)),
        "REAR": (radians(0), radians(0), radians(180)),
    }

    def __init__(self) -> None:
        self.set_frames()
        init_render_settings()
        set_default_compositing()
        self.collection = cu.get_collection("Studio")

        self.is_pcb: bool = False
        self.is_collection: bool = False
        self.is_object: bool = False
        self.is_ortho: bool = config.blendcfg["SCENE"]["ORTHO_CAM"]
        self.rendered_obj: bpy.types.Object
        self.top_parent: bpy.types.Object
        self.display_rot: int = 0
        self.top_components: List[bpy.types.Object] = []
        self.bottom_components: List[bpy.types.Object] = []
        self.cameras: List[Camera] = []
        self.backgrounds: List[Background] = []
        self.lights: List[Light] = []
        self.positions: List[str]
        self.animation_data: Dict[bpy.types.ID, bpy.types.Action | None]

        self._load_animation_data()
        self._configure_model_data()
        self._configure_position()

        self._add_cameras()
        self._add_lights()
        self._add_backgrounds()
        self._apply_effects()

        if config.blendcfg["SETTINGS"]["SAVE_SCENE"]:
            blend_scene_path = config.pcb_blend_path.replace(".blend", "_scene.blend")
            cu.save_pcb_blend(blend_scene_path)

    def _add_cameras(self) -> None:
        Camera.add_collection()

        for camera_name, _ in Camera.presets.items():
            Camera(camera_name, Camera.presets[camera_name])

        if config.blendcfg["CAMERAS"]["CUSTOM"]:
            if camera_custom := bpy.data.objects.get("camera_custom"):
                Camera(camera=camera_custom)
            else:
                logger.warning(
                    f"[CAMERAS][CUSTOM] enabled but no 'camera_custom' predefined object found in Blender file."
                )
        for position, _ in Studio.presets.items():
            self.change_position(position)
            with Bounds(cu.select_all(self.rendered_obj)) as target:
                for camera in Camera.objects:
                    camera.align(self.rendered_obj, target)
                    camera.save_position(position)
                    camera.save_focus(position)

        logger.info(f"Added {len(Camera.objects)} cameras to Studio: {[cam.object.name for cam in Camera.objects]}")

        cfg_cameras = [key for key, val in config.blendcfg["CAMERAS"].items() if val]
        cfg_pos = [key for key, val in config.blendcfg["POSITIONS"].items() if val]
        self.cameras = [cam for cam in Camera.objects if cam.name in cfg_cameras]
        self.positions = [pos for pos in Studio.presets if pos in cfg_pos]
        self.change_position("TOP")
        for camera in Camera.objects:
            camera.change_position("TOP")

    def _add_backgrounds(self) -> None:
        Background.add_collection()

        for bg_name in Background.files:
            Background(bg_name)

        Background.update_position(self.top_parent)
        logger.info(
            f"Added {len(Background.objects)} backgrounds to Studio: {[bg.object.name for bg in Background.objects]}"
        )

        cfg_bgs = config.blendcfg["BACKGROUNDS"]["LIST"]
        self.backgrounds = [bg for bg in Background.objects if bg.name in cfg_bgs]
        if missing_bgs := [bg for bg in cfg_bgs if bg not in {bg.name for bg in self.backgrounds}]:
            logger.warning("No such background: %s", missing_bgs)

    def _add_lights(self) -> None:
        Light.add_collection()

        for light_name in Light.presets:
            Light(light_name, *Light.presets[light_name])

        Light.update(self.top_parent)
        logger.info(f"Added {len(Light.objects)} lights to Studio: {[light.object.name for light in Light.objects]}")
        self.lights = Light.objects

    def _apply_effects(self) -> None:
        """Enable or disable additional studio effects"""
        if not config.blendcfg["SCENE"]["LED_ON"]:
            disable_emission_nodes()

    def _load_animation_data(self) -> None:
        """Prepare animation data backup."""
        depsgraph = bpy.context.evaluated_depsgraph_get()
        backup_data: Dict[bpy.types.ID, bpy.types.Action | None] = {}
        for bl_id in depsgraph.ids:
            data = getattr(bl_id, "animation_data", None)
            backup_data[bl_id.original] = None
            if not data or not data.action:
                continue
            if isinstance(bl_id.original, bpy.types.Object):
                cu.anim_to_deltas(bl_id.original)
            data = getattr(bl_id, "animation_data", None)
            backup_data[bl_id.original] = data.action.copy()  # type:ignore

        self.animation_data = backup_data
        self.clear_animation_data()

    def _configure_model_data(self) -> None:
        """Assign configurational attributes' values based on loaded model contents."""
        logger.info("Configuring studio...")

        obj_type, rendered_obj_name = "", ""
        if config.blendcfg["SCENE"]["RENDERED_OBJECT"]:
            obj_type = config.blendcfg["SCENE"]["RENDERED_OBJECT"][0]
            rendered_obj_name = config.blendcfg["SCENE"]["RENDERED_OBJECT"][1]

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

    def _configure_as_PCB(self) -> None:
        self.is_pcb = True
        self.top_parent = bpy.data.objects.get(config.PCB_name)
        if not self.top_parent:
            raise RuntimeError(f"{config.PCB_name} object could not be found in Blender model data.")
        self.rendered_obj = self.top_parent
        self.components = cu.select_all(self.top_parent)
        self._get_top_bottom_components()

    def _configure_as_collection(self, collection_name: str) -> None:
        self.is_collection = True
        rendered_col = bpy.data.collections.get(collection_name)
        if not rendered_col:
            raise RuntimeError(f"{collection_name} collection could not be found in Blender model data.")
        scene_components = [object for object in bpy.data.objects]
        rendered_components = [object for object in rendered_col.objects]
        self._get_top_bottom_components(rendered_components)
        self.rendered_obj = cu.add_empty("_rendered_parent", children=rendered_components)
        self.top_parent = cu.add_empty("_parent", children=scene_components, origin_source=rendered_components)
        cu.parent_list_to_object([self.rendered_obj], self.top_parent)

    def _configure_as_singleobject(self, object_name: str) -> None:
        self.is_object = True
        self.rendered_obj = bpy.data.objects.get(object_name)
        if not self.rendered_obj:
            raise RuntimeError(f"{object_name} object could not be found in Blender model data.")
        scene_components = [object for object in bpy.data.objects]
        self._get_top_bottom_components(scene_components)
        self.top_parent = cu.add_empty("_parent", children=scene_components, origin_source=[self.rendered_obj])
        cu.set_origin(self.rendered_obj)  # needed to correctly calculate focus

    def _configure_as_unknown(self) -> None:
        scene_components = [object for object in bpy.data.objects]
        self.top_parent = cu.add_empty("_parent", children=scene_components)
        self.rendered_obj = self.top_parent
        self._get_top_bottom_components(scene_components)

    def _configure_position(self) -> None:
        """
        Adjust model position before render and assign values to positions dict.
        When selected object is a child, rotates and moves top parent.
        """
        object = cu.get_top_parent(self.rendered_obj)

        if config.blendcfg["SCENE"]["ADJUST_POS"]:
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
                if "PCB_Side" not in comp.keys():  # type: ignore
                    continue
                if comp.library:
                    continue
                if comp["PCB_Side"] == "T":
                    top_comps.append(comp)
                elif comp["PCB_Side"] == "B":
                    bot_comps.append(comp)
        else:
            top_comps = [obj for obj in objects if not obj.name.startswith("_") and not obj.library]
            bot_comps = top_comps.copy()
        logger.debug(f"Read top components: {top_comps}")
        logger.debug(f"Read bot components: {bot_comps}")
        self.top_components = top_comps
        self.bottom_components = bot_comps

    def change_position(self, key: str) -> None:
        """
        Move rendered_object to position saved in dictionary.
        """
        self.top_parent.rotation_euler = self.presets[key]
        logger.debug(f"Moved {self.rendered_obj.name} to '{key}' position")
        cu.update_depsgraph()

    def set_frames(self, default: bool = False) -> None:
        """
        Set start and end frames based on the values from configuration file or existing keyframes.
        When called, updates context scene start and end values as well.
        """
        keyframes = self.get_keyframe_range(default)
        self.frame_start = keyframes[0]
        self.frame_end = keyframes[1]

        scene = bpy.context.scene
        scene.frame_start = self.frame_start
        scene.frame_end = self.frame_end
        scene.frame_set(self.frame_start)

        logger.debug(f"Set frames: start={self.frame_start}, end={self.frame_end}, current={self.frame_start}")

    def get_keyframe_range(self, default: bool) -> Tuple[int, int]:
        """
        Get keyframe range from all keyframes defined in loaded animation data or based on default config values.
        """
        if not hasattr(self, "animation_data") or not any(self.animation_data.values()) or default:
            return (1, config.blendcfg["RENDERER"]["FPS"])

        x = min([action.frame_range.x for action in self.animation_data.values() if action])
        y = max([action.frame_range.y for action in self.animation_data.values() if action])
        return (int(x), int(y))

    def add_studio_keyframes(self, camera: Camera) -> None:
        """Add keyframes to studio objects on every frame from the user animation."""
        for frame in range(self.frame_start, self.frame_end + 1):
            bpy.context.scene.frame_set(frame)
            Light.update(self.top_parent)
            Light.keyframe_all(frame)

            Background.update_position(self.top_parent)
            Background.keyframe_all(frame)

            camera.add_intermediate_keyframe(
                rendered_obj=self.rendered_obj, frame=frame, frame_selected=True, focus=True
            )
        bpy.context.scene.frame_set(self.frame_start)

    @staticmethod
    def clear_animation_data() -> None:
        """Clear existing animation data. This leaves Studio backup animation data intact if it's been loaded."""
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for bl_id in depsgraph.ids:
            bl_id.original.animation_data_clear()  # type: ignore
