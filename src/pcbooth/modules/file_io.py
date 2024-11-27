"""Module performing input/output operations on files."""

import bpy
import logging
from os import listdir
from pathlib import Path
from typing import Optional, List, Callable

import pcbooth.modules.config as config

logger = logging.getLogger(__name__)

DEFAULT_PCB_NAME = "unknownpcb"


def read_pcb_name_from_prj(path: str, extension: str) -> str:
    """Try reading the PCB name from a project file at `path` using extension specified in config.

    This function will fail and throw a `RuntimeError` if `path` is
    not a valid project directory.
    """
    files = listdir(path)
    project_file = [f for f in files if f.endswith(extension)]

    if len(project_file) != 1:
        logger.error(
            f"There should be only one {extension} file in project main directory!"
        )
        logger.error("Found: " + repr(project_file))
        raise RuntimeError(
            f"Expected single {extension} file in current directory, got %d"
            % len(project_file)
        )

    name = Path(project_file[0]).stem
    logger.debug("PCB name: %s", name)
    return name


def read_pcb_name(path: str) -> str:
    """Read the PCB name from the current EDA project."""
    extension = config.blendcfg["SETTINGS"]["PRJ_EXTENSION"]
    if extension != "":
        try:
            return read_pcb_name_from_prj(path, extension)
        except Exception:
            logger.warning(f"Failed to find {extension} file!")
        # further logic can be added in a similar way as above

    # default case
    logger.warning("Using default value for PCB name")
    return DEFAULT_PCB_NAME


def get_data_from_blendfile(
    blendfile: str, data_type: str, filter_func: Callable[[str], bool] = lambda x: True
) -> Optional[List[str]]:
    """List data from another Blender file without including it in current file."""
    result = None
    try:
        with bpy.data.libraries.load(blendfile) as (data_from, data_to):
            result = list(filter(filter_func, getattr(data_from, data_type)))
            logger.debug("Found data " + data_type + " in file " + blendfile)
    except Exception:
        logger.error("Failed to open blend file " + blendfile)
    return result


def link_collection_from_blendfile(
    blendfile: str, collection_name: str
) -> bpy.types.Object | None:
    """
    Link collection data from another Blender file.
    """
    section = "/Collection/"
    filepath = blendfile + section + collection_name
    directory = blendfile + section
    bpy.ops.wm.link(
        filepath=filepath,  # full path to .blend with /Collection/collection name
        directory=directory,  # full path to .blend with /Collection
        filename=collection_name,  # collection name
        active_collection=True,
    )

    # return last object that starts with collection_name (in case it got appended with index)
    object = [
        obj
        for obj in bpy.data.objects
        if obj.name.startswith(collection_name) and not obj.library
    ][-1]
    if isinstance(object, bpy.types.Object):
        logger.debug(f"Linked {collection_name} from {blendfile}")
        return object
    logger.debug(f"Failed to link {collection_name} from {blendfile}")
    return None
