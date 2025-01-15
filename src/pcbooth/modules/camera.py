"""Module handling cameras configuration and positioning."""

import bpy
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.bounding_box import Bounds
import pcbooth.modules.config as config
from math import radians
from mathutils import Matrix
from typing import Generator, Tuple, Dict, List, ClassVar, Any, Tuple, Optional
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Camera:
    objects: ClassVar[List["Camera"]] = []
    collection: bpy.types.Collection

    presets = {
        "TOP": (radians(0), radians(0), radians(0)),
        "ISO": (radians(54.736), radians(0), radians(45)),
        "FRONT": (radians(30), radians(0), radians(0)),
        "LEFT": (radians(190), radians(-155), radians(-200)),
        "RIGHT": (radians(190), radians(-200), radians(-155)),
        "PHOTO1": (radians(38), radians(0), radians(13)),
        "PHOTO2": (radians(60), radians(0), radians(20)),
    }

    @classmethod
    def add_collection(cls) -> None:
        """Create new Cameras collection"""
        studio = cu.get_collection("Studio")
        collection = cu.get_collection("Cameras", studio)
        cls.collection = collection

    @classmethod
    def get(cls, name: str) -> Optional["Camera"]:
        """Get Camera object by name string."""
        for object in cls.objects:
            if object.name == name:
                return object
        logger.warning(f"Camera: {name} not found.")
        return None

    def __init__(
        self,
        name: str = "",
        rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        camera: Optional[bpy.types.Object] = None,
    ) -> None:
        if not Camera.collection:
            raise ValueError(
                f"Camera collection is not added, call add_collection class method before creating an instance."
            )

        self.positions: Dict[str, Matrix] = {}
        self.focuses: Dict[str, Tuple[float, float]] = {}
        self.name = name
        self.object: bpy.types.Object = self._add(name, rotation, camera)
        self._set_defaults()

    def _add(
        self,
        name: str = "",
        rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        camera: Optional[bpy.types.Object] = None,
    ) -> bpy.types.Object:
        """Add and/or create camera from either existing object or using specified name and rotation"""
        if camera:
            # in case camera is already predefined in .blend is to be added as Camera (custom camera handling)
            object = camera
            self.name = "CUSTOM"
        else:
            camera_name = "camera_" + name.lower()
            new_camera = bpy.data.cameras.new(camera_name)
            object = bpy.data.objects.new(camera_name, new_camera)
            object.rotation_euler = rotation
        cu.link_obj_to_collection(object, Camera.collection)

        logger.debug(
            f"Added camera object: {object.name} at {object.rotation_euler}, {object.location}"
        )
        Camera.objects.append(self)
        return object

    def _set_defaults(self) -> None:
        """Set default camera properties"""
        self.object.data.type = "PERSP"  # type: ignore
        self.object.data.lens = 1000 if config.blendcfg["SCENE"]["ORTHO_CAM"] else 105  # type: ignore
        self.object.data.clip_start = 0.1  # type: ignore
        self.object.data.clip_end = 15000  # type: ignore # set long clip end for renders
        if config.blendcfg["SCENE"]["DEPTH_OF_FIELD"]:
            self.object.data.dof.use_dof = True  # type: ignore
        self._sensor_default: float = 36.0
        self._sensor_zoomedout: float = (
            config.blendcfg["SCENE"]["ZOOM_OUT"] * self._sensor_default
        )

    def save_position(self, key: str) -> None:
        """
        Save position of the camera to the dictionary under provided key.
        """
        cu.update_depsgraph()
        self.positions[key] = self.object.matrix_world.copy()
        logger.debug(
            f"Saved {self.object.name} location: \n{self.positions[key]} as '{key}'"
        )

    def save_focus(self, key: str) -> None:
        """
        Save focus parameters of the camera to the dictionary under provided key.
        Value is a tuple of (focus_distance, aperture_fstop)
        """
        self.focuses[key] = (
            self.object.data.dof.focus_distance,  # type: ignore
            self.object.data.dof.aperture_fstop,  # type: ignore
        )
        logger.debug(
            f"Saved {self.object.name} focus: \n{self.focuses[key]} as '{key}'"
        )

    def change_position(self, key: str) -> None:
        """
        Move camera to position saved in dictionary. Updates focus as well.
        """
        self.object.matrix_world = self.positions[key].copy()
        self.change_focus(key)
        logger.debug(f"Moved {self.object.name} to '{key}' position.")
        cu.update_depsgraph()

    def change_focus(self, key: str) -> None:
        """
        Use camera focus parameters from position saved in dictionary.
        """
        self.object.data.dof.focus_distance = self.focuses[key][0]  # type: ignore
        self.object.data.dof.aperture_fstop = self.focuses[key][1]  # type: ignore
        logger.debug(f"Changed focus of {self.object.name} to '{key}' position.")

    def frame_selected(self, object: bpy.types.Object) -> None:
        """
        Align selected camera to frame all rendered objects.
        Applies zoom out afterwards (zoom_out < 1 - zoom in, zoom_out > 1 - zoom out).
        """
        self.object.data.sensor_width = self._sensor_default  # type: ignore
        cu.select_all(object)
        bpy.context.scene.camera = self.object
        bpy.ops.view3d.camera_to_view_selected()
        bpy.ops.object.select_all(action="DESELECT")
        self.object.data.sensor_width = self._sensor_zoomedout  # type: ignore

        cu.update_depsgraph()

        logger.debug(f"frame_selected function used for {self.object.name}")

    def set_focus(self, object: bpy.types.Object) -> None:
        """
        Calculate focus distance based on the distance between camera and rendered object.
        Apply focal ratio.
        """
        cu.set_origin(object)
        self.object.data.dof.focus_distance = abs(  # type: ignore
            (object.location - self.object.location).length
        )
        cfg_f_ratio = config.blendcfg["SCENE"]["FOCAL_RATIO"]
        self.object.data.dof.aperture_fstop = (  # type: ignore
            self._calculate_focal_ratio() if cfg_f_ratio == "auto" else cfg_f_ratio
        )
        logger.debug(f"set_focus function used for {self.object.name}")

    def _calculate_focal_ratio(self) -> float:
        """
        Calculate focal ratio relative to focus distance.
        Multiplier can be adjusted to control the blur (higher values result in sharper image).
        """
        multiplier = 9.5
        focal_ratio = (
            1
            / self.object.data.dof.focus_distance  # type: ignore
            * multiplier
            * (10 if config.blendcfg["SCENE"]["ORTHO_CAM"] else 1)
        )

        logger.debug(f"Calculated focal ratio: {focal_ratio}")
        return focal_ratio

    def align(self, object: bpy.types.Object, target: Bounds) -> None:
        """
        Align camera to all rendered objects and then recalculate focus distance.
        """
        self.frame_selected(object)
        self.set_focus(target.bounds)

    def add_keyframe(
        self,
        frame: int,
        translations: bool = True,
        focus: bool = True,
        zoom_out: bool = True,
    ) -> None:
        """
        Add keyframe operation to be performed after changing camera position and/or focus.
        Keyframe is added at specified frame.
        """
        if translations:
            self.object.keyframe_insert(data_path="rotation_euler", frame=frame)
            self.object.keyframe_insert(data_path="location", frame=frame)
        if zoom_out:
            self.object.data.keyframe_insert(data_path="sensor_width", frame=frame)
        if focus:
            self.object.data.dof.keyframe_insert(  # type: ignore
                data_path="focus_distance", frame=frame
            )
            self.object.data.dof.keyframe_insert(  # type: ignore
                data_path="aperture_fstop", frame=frame
            )

    def add_intermediate_keyframe(
        self,
        rendered_obj: bpy.types.Object,
        progress: float,
        zoom_out: float = 1.0,
        frame_selected: bool = True,
    ) -> None:
        """
        Insert intermediate keyframes for the camera at a specified fraction of the animation timeline, aligning it with the rendered object.
        This ensures the object remains within the camera frame during interpolated movement. The method also allows optional adjustment of the
        camera's position by applying a zoom factor.
        """
        scene = bpy.context.scene

        scene.frame_set(int(scene.frame_end * progress))
        if frame_selected:
            self.frame_selected(rendered_obj)

        self.object.data.sensor_width = self._sensor_zoomedout * zoom_out  # type: ignore

        if config.blendcfg["SCENE"]["ORTHO_CAM"]:
            self.set_focus(rendered_obj)

        self.add_keyframe(
            scene.frame_current,
            focus=config.blendcfg["SCENE"]["ORTHO_CAM"],
        )

    @contextmanager
    def dof_override(self) -> Generator[None, Any, None]:
        """Temporarily disable depth of field of the camera."""
        try:
            self.object.data.dof.use_dof = False  # type: ignore
            yield
        except AttributeError:
            pass
        finally:
            if config.blendcfg["SCENE"]["DEPTH_OF_FIELD"]:
                self.object.data.dof.use_dof = True  # type: ignore
