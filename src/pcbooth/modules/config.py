"""Module for configuring input data."""

import argparse
import logging
from os import getcwd, path
from typing import Dict, Any
import pcbooth.modules.file_io as fio
import pcbooth.core.blendcfg as bcfg

blendcfg: Dict[str, Any] = {}
prj_path: str = ""
pcbt_dir_path: str = ""

fab_path: str = ""
env_texture_path: str = ""
backgrounds_path: str = ""
renders_path: str = ""
animations_path: str = ""
PCB_name: str = ""
pcb_blend_path: str = ""

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
    args = arguments


def configure_paths(arguments: argparse.Namespace) -> None:
    """Configure global paths that will be searched for HW files.

    Args:
    ----
        arguments: CLI arguments

    """

    global fab_path
    global env_texture_path
    global backgrounds_path
    global renders_path
    global animations_path
    global pcb_blend_path
    global PCB_name

    env_texture_path = pcbt_dir_path + "/templates/studio_small_08_4k.exr"
    backgrounds_path = pcbt_dir_path + "/templates/backgrounds/"
    renders_path = prj_path + blendcfg["SETTINGS"]["RENDER_DIR"] + "/"
    animations_path = prj_path + blendcfg["SETTINGS"]["ANIMATION_DIR"] + "/"

    # Determine blend_path
    if arguments.blend_path is None:
        project_extension = blendcfg["SETTINGS"]["PRJ_EXTENSION"]
        fab_path = prj_path + blendcfg["SETTINGS"]["FAB_DIR"] + "/"
        if not path.isdir(fab_path):
            raise RuntimeError(
                f"There is no {blendcfg['SETTINGS']['FAB_DIR']}/ directory in the current working directory! ({prj_path})"
            )
        PCB_name = fio.read_pcb_name_from_prj(prj_path, project_extension)
        pcb_blend_path = fab_path + PCB_name + ".blend"
    else:
        PCB_name = arguments.blend_path.split("/")[-1].replace(".blend", "")
        pcb_blend_path = path.abspath(arguments.blend_path)

    if not path.exists(pcb_blend_path):
        raise RuntimeError(
            f"There is no .blend file in expected directory! ({pcb_blend_path})"
        )
