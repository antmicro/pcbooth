"""Module performing input/output operations on files."""

import bpy
import logging
import os
import sys
from pathlib import Path
from contextlib import contextmanager
from subprocess import run, DEVNULL, PIPE
from typing import Generator, Optional, List, Callable, Literal, Any
from io import TextIOWrapper

import pcbooth.modules.config as config

logger = logging.getLogger(__name__)

DEFAULT_PCB_NAME = "unknownpcb"


def read_pcb_name_from_prj(path: str, extension: str) -> str:
    """Try reading the PCB name from a project file at `path` using extension specified in config.

    This function will fail and throw a `RuntimeError` if `path` is
    not a valid project directory.
    """
    files = os.listdir(path)
    project_file = [f for f in files if f.endswith(extension)]

    if len(project_file) != 1:
        logger.error(f"There should be only one {extension} file in project main directory!")
        logger.error("Found: " + repr(project_file))
        raise RuntimeError(f"Expected single {extension} file in current directory, got %d" % len(project_file))

    name = Path(project_file[0]).stem
    logger.debug("PCB name: %s", name)
    return name


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


def link_collection_from_blendfile(blendfile: str, collection_name: str) -> bpy.types.Object | None:
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
    object = [obj for obj in bpy.data.objects if obj.name.startswith(collection_name) and not obj.library][-1]
    if isinstance(object, bpy.types.Object):
        logger.debug(f"Linked {collection_name} from {blendfile}")
        return object
    logger.debug(f"Failed to link {collection_name} from {blendfile}")
    return None


@contextmanager
def stdout_redirected(to: str = os.devnull) -> Generator[None, Any, None]:
    """
    Redirect the standard output to dev/null.

    This context manager temporarily redirects `sys.stdout` to a specified target file or stream.
    During the redirection, any output written to `print()` or `sys.stdout` will be written to the target
    instead of the original `stdout`. After exiting the context, `sys.stdout` is restored to its original state.

    https://blender.stackexchange.com/questions/6119/suppress-output-of-python-operators-bpy-ops
    """

    fd = sys.stdout.fileno()

    def _redirect_stdout(to: TextIOWrapper) -> None:
        sys.stdout.close()  # + implicit flush()
        os.dup2(to.fileno(), fd)  # fd writes to 'to' file
        sys.stdout = os.fdopen(fd, "w")  # Python writes to fd

    with os.fdopen(os.dup(fd), "w") as old_stdout:
        with open(to, "w") as file:
            _redirect_stdout(to=file)
        try:
            yield  # allow code to be run with the redirected stdout
        finally:
            _redirect_stdout(to=old_stdout)  # restore stdout


def mkdir(path: str) -> None:
    """Create a directory at the specified path.

    Wraps any errors with a nicer error exception.
    """
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Could not create folder at path {path}: {repr(e)}") from e


def remove_file(filepath: str) -> None:
    """Remove file from the specified path."""
    try:
        os.remove(filepath)
        logger.debug(f"Removed {filepath}")
    except (FileNotFoundError, IsADirectoryError):
        pass


def execute_cmd(
    cmd_list: List[str],
    stdout: bool = False,
    stderr: bool = False,
    level: Literal["info", "debug", "warning", "error" "critical"] = "debug",
) -> None:
    """Execute command using Subprocess module. stderr and stdout can be passed to logger with varying level."""

    stdout_val = PIPE if stdout else DEVNULL
    stderr_val = PIPE if stderr else DEVNULL
    log = run(
        cmd_list,
        check=True,
        text=True,
        stdout=stdout_val,
        stderr=stderr_val,
    )
    logger = getattr(logging, level)
    logger(log.stdout)
    logger(log.stderr)
