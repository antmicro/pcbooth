"""Module handling backgrounds configuration and positioning."""

import bpy
import logging
from typing import List, ClassVar

import pcbooth.modules.config as config
import pcbooth.modules.file_io as fio
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.bounding_box import Bounds


logger = logging.getLogger(__name__)


class Background:
    objects: ClassVar[List["Background"]] = []
    collection: bpy.types.Collection = None

    @classmethod
    def add_collection(cls):
        """Create new Backgrounds collection"""
        studio = cu.get_collection("Studio")
        collection = cu.get_collection("Backgrounds", studio)
        cls.collection = collection

    @classmethod
    def update_position(cls, object: bpy.types.Object):
        """Update position of all imported backgrounds in relation to current lowest point of rendered object"""
        with Bounds(cu.select_all(object)) as target:
            for bg in cls.objects:
                bg.object.location.z = target.min_z
        logger.debug(f"Backgrounds moved to Z: {bg.object.location.z}")
        cu.update_depsgraph()

    @classmethod
    def use(cls, name: str = ""):
        """Make specified background enabled for rendering"""
        for bg in cls.objects:
            bg.object.hide_render = True
        if background := bpy.data.objects.get(name):
            background.hide_render = False
            logger.debug(f"Enabling '{name}' background for render.")
        else:
            logger.warning(f"Requested background '{name}' was not found!")

    def __init__(self, name: str = ""):
        if not Background.collection:
            raise ValueError(
                f"Backgrounds collection is not added, call add_collection class method before creating an instance."
            )

        self.object: bpy.types.Object = self._add(name)

    def _add(self, name: str = "") -> bpy.types.Object:
        """
        Link background collections from src/pcbooth/templates/backgrounds/ using name string.
        First collection found in background .blend file is linked.
        Result object name is changed to the input name string.
        """
        blendfile = config.backgrounds_path + name + ".blend"
        object = None
        if name == "transparent":
            object = cu.add_empty("transparent", Background.collection)
            logger.debug(f"Added background placeholder object: {object.name}")

        elif bg_data := fio.get_data_from_blendfile(blendfile, "collections"):
            bg_collection = bg_data[0]
            object = fio.link_collection_from_blendfile(blendfile, bg_collection)
            cu.link_obj_to_collection(object, Background.collection)
            logger.debug(
                f"Added background linked object: {object.name} from {blendfile}"
            )

        if not object:
            logger.debug(f"'{name}' background not added!")
            return object

        object.name = name
        object.location.z = 0
        object.hide_render = True
        object.hide_viewport = True
        Background.objects.append(self)
        return object
