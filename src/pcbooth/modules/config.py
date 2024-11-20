"""Module for configuring input data."""

import bpy
import argparse
import logging
from os import getcwd, path
from typing import Dict, Any, List
import pcbooth.modules.fileIO as fio
import pcbooth.core.blendcfg as bcfg
import pcbooth.modules.custom_utilities as cu
import pcbooth.modules.bounding_box as bb

blendcfg: Dict[str, Any] = {}
prj_path: str = ""
pcbt_dir_path: str = ""

fab_path: str = ""
env_texture_path: str = ""
renders_path: str = ""
PCB_name: str = ""
pcb_blend_path: str = ""

isPCB: bool = False
isCollection: bool = False
isObject: bool = False
isUnknown: bool = True

rendered_obj: bpy.types.Object = None
display_rot: int = 0
top_components: List[str] = []
bottom_components: List[str] = []

args: argparse.Namespace


logger = logging.getLogger(__name__)


def init_global(arguments: argparse.Namespace) -> None:
    """Initialize global variables used across modules.

    Args:
    ----
        arguments: CLI arguments

    """

    global blendcfg
    global prj_path
    global pcbt_dir_path

    global args

    prj_path = getcwd() + "/"
    pcbt_dir_path = path.dirname(__file__) + "/.."

    # Create blendcfg if it does not exist
    bcfg.check_and_copy_blendcfg(prj_path, pcbt_dir_path)
    # Read blendcfg file
    blendcfg = bcfg.open_blendcfg(prj_path, arguments.config_preset, pcbt_dir_path)

    configure_paths(arguments)
    cu.open_blendfile(pcb_blend_path)
    configure_model_data()

    args = arguments


def configure_paths(arguments: argparse.Namespace) -> None:
    """Configure global paths that will be searched for HW files.

    Args:
    ----
        arguments: CLI arguments

    """

    global fab_path
    global env_texture_path
    global renders_path
    global animations_path
    global pcb_blend_path
    global PCB_name

    env_texture_path = pcbt_dir_path + "/templates/studio_small_03_4k.exr"
    renders_path = prj_path + blendcfg["SETTINGS"]["RENDER_DIR"] + "/"
    animations_path = prj_path + blendcfg["SETTINGS"]["ANIMATION_DIR"] + "/"
    # hotareas_path = project_path + "assets/hotareas/"

    # Determine blend_path
    if arguments.blend_path is None:
        project_extension = blendcfg["SETTINGS"]["PRJ_EXTENSION"]
        fab_path = prj_path + blendcfg["SETTINGS"]["FAB_DIR"] + "/"
        if not path.isdir(fab_path):
            raise RuntimeError(
                f"There is no {blendcfg['SETTINGS']['FAB_DIR']}/ directory in the current working directory! ({prj_path})"
            )
        PCB_name = fio.read_pcb_name(prj_path, project_extension)
        pcb_blend_path = fab_path + PCB_name + ".blend"
    else:
        PCB_name = arguments.blend_path.split("/")[-1].replace(".blend", "")
        pcb_blend_path = path.abspath(arguments.blend_path)

    if not path.exists(pcb_blend_path):
        raise RuntimeError(
            f"There is no .blend file in expected directory! ({pcb_blend_path})"
        )


def configure_model_data():
    """ """
    global isPCB
    global isCollection
    global isObject
    global isUnknown
    global rendered_obj
    global display_rot
    global top_components
    global bottom_components

    obj_type, rendered_obj_name = "", ""
    if blendcfg["OBJECT"]["RENDERED_OBJECT"]:
        obj_type = blendcfg["OBJECT"]["RENDERED_OBJECT"][0]
        rendered_obj_name = blendcfg["OBJECT"]["RENDERED_OBJECT"][1]

    # single custom object picked using RENDERED_OBJECT setting
    if obj_type == "Object":
        logger.info(f"Rendering from object: {rendered_obj_name}")
        configure_as_singleobject(rendered_obj_name, adjust_pos=False)
        return

    # single collection picked using RENDERED_COLLECTION setting:
    # will work as Assembly collection before
    if obj_type == "Collection":
        logger.info(f"Rendering from collection: {rendered_obj_name}")
        configure_as_collection(rendered_obj_name)
        return

    # PCB generated using gerber2blend
    # can be without components
    if bpy.data.collections.get("Board") and bpy.data.objects.get(PCB_name):
        logger.info("PCB type model was recognized.")
        configure_as_PCB(PCB_name)
        return

    # Unknown type model
    # check if there's only one object
    # if there's more, treat it as collection
    logger.info("Unknown type model was recognized.")
    if len(bpy.data.objects) == 1:
        rendered_obj_name = bpy.data.objects[0].name
        configure_as_singleobject(rendered_obj_name, adjust_pos=True)
    else:
        configure_as_unknown()


def configure_as_PCB(object_name):
    global rendered_obj, top_components, bottom_components, isUnknown, isPCB
    rendered_obj = bpy.data.objects.get(object_name, "")
    if not rendered_obj:
        raise RuntimeError(
            f"{object_name} object could not be found in Blender model data."
        )
    top_components, bottom_components = cu.get_top_bottom_component_lists()
    isUnknown = False
    isPCB = True
    components_col = bpy.data.collections.get("Components")
    components = [object for object in components_col.objects]
    bbox_obj = bb.generate_bbox(components + [rendered_obj])
    cu.parent_list_to_object([bbox_obj], rendered_obj)


def configure_as_collection(collection_name):
    global rendered_obj, top_components, bottom_components, isUnknown, isCollection
    rendered_col = bpy.data.collections.get(collection_name, "")
    if not rendered_col:
        raise RuntimeError(
            f"{collection_name} collection could not be found in Blender model data."
        )
    components = [object for object in rendered_col.objects]
    rendered_obj = bb.generate_bbox(components)
    top_components, bottom_components = cu.get_top_bottom_component_lists(
        components, enable_all=True
    )
    isUnknown = False
    isCollection = True
    cu.link_obj_to_collection(rendered_obj, rendered_col)
    cu.parent_list_to_object(components, rendered_obj)


def configure_as_singleobject(object_name, adjust_pos=True):
    global rendered_obj, top_components, bottom_components, isUnknown, isObject, display_rot
    rendered_obj = bpy.data.objects.get(object_name, "")
    if not rendered_obj:
        raise RuntimeError(
            f"{object_name} object could not be found in Blender model data."
        )
    isUnknown = False
    isObject = True
    if adjust_pos:
        display_rot = rendered_obj.get("DISPLAY_ROT", 0)
        cu.center_on_scene(rendered_obj)
    else:
        display_rot = 0


def configure_as_unknown():
    global rendered_obj, top_components, bottom_components
    components = [object for object in bpy.data.objects]
    rendered_obj = bb.generate_bbox(components)
    top_components, bottom_components = cu.get_top_bottom_component_lists(
        components, enable_all=True
    )
    cu.parent_list_to_object(components, rendered_obj)
