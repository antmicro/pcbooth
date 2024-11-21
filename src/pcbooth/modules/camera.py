import bpy
from pcbooth.modules.custom_utilities import (
    select_all,
    link_obj_to_collection,
    get_collection,
)
import pcbooth.modules.config as config
from math import radians
from mathutils import Matrix
from typing import Tuple, Dict, List, ClassVar
import logging

logger = logging.getLogger(__name__)


class Camera:
    objects: ClassVar[List["Camera"]] = []
    collection: bpy.types.Collection = None

    presets = {
        "TOP": (radians(0), radians(0), radians(0)),
        "ISO": (radians(54.736), radians(0), radians(45)),
        "FRONT": (radians(30), radians(0), radians(0)),
        "LEFT": (radians(190), radians(-156), radians(-197)),
        "RIGHT": (radians(200), radians(-205), radians(-155)),
        "PHOTO1": (radians(38), radians(0), radians(13)),
        "PHOTO2": (radians(60), radians(0), radians(20)),
    }

    @classmethod
    def add_collection(cls):
        """Create new Cameras collection"""
        studio = get_collection("Studio")
        collection = get_collection("Cameras", studio)
        cls.collection = collection

    def __init__(
        self,
        name: str = "",
        rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        camera: bpy.types.Object = None,
    ):
        if not Camera.collection:
            raise ValueError(
                f"Camera collection is not added, call add_collection class method before creating an instance."
            )

        self.positions: Dict[str, mathutils.Matrix] = {}
        self.object: bpy.types.Object = self._add(name, rotation, camera)
        self._set_defaults()

    def _add(
        self,
        name: str = "",
        rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        camera: bpy.types.Object = None,
    ) -> bpy.types.Object:
        """Add and/or create camera from either existing object or using specified name and rotation"""
        if camera:
            # in case camera is already predefined in .blend is to be added as Camera (custom camera handling)
            object = camera
        else:
            camera_name = "camera_" + name.lower()
            camera = bpy.data.cameras.new(camera_name)
            object = bpy.data.objects.new(camera_name, camera)
            object.rotation_euler = rotation
        link_obj_to_collection(object, Camera.collection)

        logger.debug(f"Added camera object: {object.name} at {object.rotation_euler}")
        Camera.objects.append(self)
        return object

    def _set_defaults(self) -> None:
        """Set default camera properties"""
        self.object.data.type = "PERSP"
        self.object.data.lens = (
            2000 if config.blendcfg["CAMERAS"]["ORTHO_TYPE"] else 105
        )
        self.object.data.clip_start = 0.1
        self.object.data.clip_end = 15000  # set long clip end for renders
        if config.blendcfg["STUDIO_EFFECTS"]["DEPTH_OF_FIELD"]:
            self.object.data.dof.use_dof = True

    def save_position(self, key: str):
        """
        Save position of the camera to the dictionary under provided key.
        """
        self.positions[key] = self.object.matrix_world.copy()
        logger.debug(
            f"Saved {self.object.name} location: \n{self.positions[key]} as '{key}'"
        )

    def change_position(self, key: str):
        """
        Move camera to position saved in dictionary.
        """
        self.object.matrix_world = self.positions[key].copy()
        logger.debug(f"Moved {self.object.name} to '{key}' position")

    def frame_selected(
        self,
        rendered_obj: bpy.types.Object,
        zoom: float = 1.05,
    ):
        """
        Align selected camera to frame all rendered objects.
        Applies zoom afterwards (zoom < 1 - zoom in, zoom > 1 - zoom out).
        TBD: add zoom to blendcfg?
        """
        select_all(rendered_obj)
        bpy.context.scene.camera = self.object
        bpy.ops.view3d.camera_to_view_selected()
        bpy.ops.object.select_all(action="DESELECT")
        self.object.location *= zoom

        logger.debug(f"frame_selected function used for {self.object.name}")

    def set_focus(
        self,
        rendered_obj: bpy.types.Object,
        focal_ratio: float = 0.0625,
    ):
        """
        Calculate focus distance based on the distance between camera and rendered object.
        Apply focal ratio.
        TBD: add focal_ratio to blendcfg?
        """

        self.object.data.dof.focus_distance = abs(
            (rendered_obj.location - self.object.location).length
        )
        self.object.data.dof.aperture_fstop = focal_ratio

        logger.debug(f"set_focus function used for {self.object.name}")

    def align(self, rendered_obj: bpy.types.Object, **kwargs):
        """
        Align camera to all rendered objects and then recalculate focus distance.
        Args:
            rendered_obj: bpy.types.Object
            focal_ratio: float = 0.0625
            zoom: float = 1.05
        """
        set_focus_args = {
            key: kwargs[key] for key in ["rendered_obj", "focal_ratio"] if key in kwargs
        }
        frame_selected_args = {
            key: kwargs[key] for key in ["rendered_obj", "zoom"] if key in kwargs
        }

        self.frame_selected(rendered_obj, **frame_selected_args)
        self.set_focus(rendered_obj, **set_focus_args)
