"""Module handling backgrounds configuration and positioning."""

import bpy
import logging
from typing import List, ClassVar, Optional

import pcbooth.modules.config as config
import pcbooth.modules.file_io as fio
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.bounding_box import Bounds
from pathlib import Path


logger = logging.getLogger(__name__)


class Background:
    objects: ClassVar[List["Background"]] = []
    collection: bpy.types.Collection
    files: List[str] = []

    @classmethod
    def add_collection(cls) -> None:
        """Create new Backgrounds collection"""
        studio = cu.get_collection("Studio")
        collection = cu.get_collection("Backgrounds", studio)
        cls.collection = collection
        cls.files = [file.stem for file in Path(config.backgrounds_path).iterdir() if file.suffix == ".blend"] + [
            "transparent"
        ]

    @classmethod
    def get(cls, name: str) -> Optional["Background"]:
        """Get Camera object by name string."""
        for object in cls.objects:
            if object.name == name:
                return object
        logger.warning(f"Background: {name} not found.")
        return None

    @classmethod
    def update_position(cls, object: bpy.types.Object) -> None:
        """Update position of all imported backgrounds in relation to current lowest point of rendered object."""
        with Bounds(cu.select_all(object)) as target:
            for bg in cls.objects:
                bg.object.location.z = target.min_z
        logger.debug(f"Backgrounds moved to Z: {bg.object.location.z}")
        cu.update_depsgraph()

    @classmethod
    def use(cls, background: "Background") -> None:
        """Make specified background enabled for rendering."""
        for bg in cls.objects:
            bg.object.hide_render = True
        background.object.hide_render = False
        logger.debug(f"Enabling '{background.object.name}' background for render.")

    @classmethod
    def keyframe_all(cls, frame: int) -> None:
        """Keyframe all Background objects."""
        for bg in cls.objects:
            bg.object.keyframe_insert(data_path="location", frame=frame)

    def __init__(self, name: str = "") -> None:
        if not Background.collection:
            raise ValueError(
                f"Backgrounds collection is not added, call add_collection class method before creating an instance."
            )
        self.name: str = name
        self.object: bpy.types.Object = self._add(name)

    def _add(self, name: str = "") -> bpy.types.Object:
        """
        Link background collections from src/pcbooth/templates/backgrounds/ using name string.
        First collection found in background .blend file is linked.
        Result object name is changed to the input name string.
        """
        blendfile = config.backgrounds_path + name + ".blend"
        if name == "transparent":
            object = cu.add_empty("transparent", Background.collection)
            logger.debug(f"Added background placeholder object: {object.name}")
            Background.objects.append(self)

        elif bg_data := fio.get_data_from_blendfile(blendfile, "collections"):
            bg_collection = bg_data[0]
            linked_object = fio.link_collection_from_blendfile(blendfile, bg_collection)
            if linked_object:
                object = linked_object
                cu.link_obj_to_collection(object, Background.collection)
                logger.debug(f"Added background linked object: {object.name} from {blendfile}")
                Background.objects.append(self)
            else:
                object = cu.add_empty(name, Background.collection)
                logger.warning(f"'{name}' background not added!")

        object.name = name
        object.location.z = 0
        object.hide_render = True
        object.hide_viewport = True
        return object
