import logging
import sys
from os import listdir, path
from pathlib import Path
from shutil import copyfile
import bpy
import hiyapyco
from xdg.BaseDirectory import load_data_paths
import pcbooth.modules.config as config
from typing import Optional, List, Callable

logger = logging.getLogger(__name__)


########################################


def is_color(arg):
    hex_chars = "0123456789ABCDEF"
    return len(arg) == 6 and all([c in hex_chars for c in arg])


def is_color_preset(arg):
    presets = ["White", "Black", "Blue", "Red", "Green"]  # allowed color keywords
    if arg in presets or is_color(arg):
        return 1


def is_transition(arg):
    first = arg[0] == "True"
    if first and len(arg) == 1:
        return False  # missing backgrounds to use
    options = ["All", "Renders", "Iso"]
    return all([opt in options for opt in arg[1:]])


# parse color
def hex_to_rgba(hex, alpha=True):
    rgb = []
    for i in (0, 2, 4):
        decimal = int(hex[i : i + 2], 16)
        rgb.append(decimal / 255)
    if alpha:
        rgb.append(1)
    return tuple(rgb)


def parse_true_false(arg):
    # change first to bool, rest remains as list of strings
    tmp = arg.replace(",", "").split()
    tmp[0] = True if tmp[0] == "True" else False
    return tmp


def parse_strings(arg):
    tmp = arg.split(",")
    tmp = [text.strip() for text in tmp]
    return tmp


########################################


def read_pcb_name(path, project_extension):
    try:
        files = listdir(path)
        filtered_ext_files = [f for f in files if f.endswith(project_extension)]
        if len(filtered_ext_files) != 1:
            logger.error(
                "There should be only one main project file in current directory!"
            )
            logger.error("Found: " + repr(filtered_ext_files))
            exit(1)
        PCB_name = Path(filtered_ext_files[0]).stem
        logger.debug("PCB_name = " + PCB_name)
    except:
        logger.warning("Failed to find main projet file!")
        exit(1)
    return PCB_name


########################################


# equivalent to file/open in GUI,
# will overwrite current file!
def open_blendfile(blendfile):
    logger.info(f"Opening existing file: {blendfile}")
    bpy.ops.wm.open_mainfile(filepath=blendfile)


def import_from_blendfile(blendfile, data_type, filter_func=lambda x: True):
    try:
        with bpy.data.libraries.load(blendfile) as (data_from, data_to):
            filtered_data = list(filter(filter_func, getattr(data_from, data_type)))
            setattr(data_to, data_type, filtered_data)
            logger.debug("found data " + data_type + " in file " + blendfile)
            return filtered_data
    except:
        logger.error("failed to open blend file " + blendfile)
    return None


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
        active_collection=False,
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
