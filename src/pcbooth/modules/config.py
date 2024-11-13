"""Module for configuring input data."""

import bpy
import argparse
import logging
from os import getcwd, path
from typing import Dict, Any, List
import pcbooth.modules.fileIO as fio
import pcbooth.core.blendcfg as bcfg
import pcbooth.modules.custom_utilities as cu

blendcfg: Dict[str, Any] = {}
fab_path: str = ""
PCB_name: str = ""
pcb_blend_path: str = ""
pcbt_dir_path: str = ""
rendered_obj: str | None
top_components: List[str | None]
bottom_components: List[str | None]
isPCB: bool
isComponent: bool
isAssembly: bool
isUnknown: bool
display_rot: int
args: argparse.Namespace


logger = logging.getLogger(__name__)


def init_global(arguments: argparse.Namespace) -> None:
    """Initialize global variables used across modules.

    Args:
    ----
        arguments: CLI arguments

    """

    global prj_path
    global blendcfg
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
    configure_model()

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
    global pcb_blend_path
    global PCB_name
    global prj_path

    env_texture_path = pcbt_dir_path + "/templates/studio_small_03_4k.exr"
    renders_path = prj_path + blendcfg["SETTINGS"]["RENDER_DIR"] + "/"
    # anim_path = project_path + "assets/previews/"
    # hotareas_path = project_path + "assets/hotareas/"

    # Determine the name of the PCB to use as a name for the .blend

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


def configure_model():
    """ """
    global isPCB
    global isAssembly
    global isCustom
    global isUnknown
    global rendered_obj
    global display_rot
    global top_components
    global bottom_components

    rendered_obj = None
    isPCB = False
    isAssembly = False
    isCustom = False
    isUnknown = True
    display_rot = 0
    top_components = []
    bottom_components = []

    with bpy.data.libraries.load(pcb_blend_path) as (data_from, _):
        if blendcfg["OBJECT"]["RENDERED_OBJ"]:
            logger.info(
                f"Setting {rendered_obj} as rendered object (picked by user in blendcfg)"
            )
            isCustom = True
            isUnknown = False
            rendered_obj = bpy.data.objects.get(
                blendcfg["OBJECT"]["RENDERED_OBJ"], None
            )
            display_rot = cu.get_display_rot(rendered_obj)

            return

        elif "Assembly" in data_from.collections:
            isAssembly = True
            isUnknown = False
            logger.info(f"Recognized assembly type model.")
            top_components, bottom_components = cu.get_top_bottom_component_lists(
                enable_all=True
            )
            # rendered object is all in Assembly collection
            return

        elif "Board" in data_from.collections and PCB_name in data_from.objects:
            logger.info(f"Recognized PCB type model.")
            isPCB = True
            isUnknown = False
            rendered_obj = bpy.data.objects.get(PCB_name, None)
            top_components, bottom_components = cu.get_top_bottom_component_lists()
            return

        else:
            logger.warning(
                "This file doesn't contain any of supported collections ('Board', 'Assembly') and the custom rendered object is not specified."
            )
            logger.warning("It will be processed as unknown type model.")
            # gets first collection first object
            rendered_obj = bpy.context.scene.collection.children[0].objects[0]
            display_rot = cu.get_display_rot(rendered_obj)
