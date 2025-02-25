import argparse
import importlib
import inspect
import logging
import os
import pkgutil
import sys
from typing import Any, Optional

import pcbooth.core.job
import pcbooth.modules.config as config
import pcbooth.core.blendcfg as blendcfg
import pcbooth.core.log as log
import pcbooth.modules.custom_utilities as cu
from pcbooth.modules.studio import Studio


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=35)

    parser = argparse.ArgumentParser(
        prog="PCBooth",
        prefix_chars="-",
        formatter_class=formatter,
        description="PCBooth - Blender scene and render generator.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        "-v",
        "--verbose",
        dest="debug",
        action="store_true",
        help="increase verbosity, print more information",
    )
    parser.add_argument(
        "-b",
        "--blend-path",
        dest="blend_path",
        help="specify path to input/output .blend file",
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_preset",
        help="",
        type=str,
        default="default",
    )
    parser.add_argument(
        "-R",
        "--reset-config",
        help="Reset local config settings to the values from the template and exit. Copy blendcfg.yaml to CWD instead if there is no CWD config file found.",
        action="store_true",
    )
    parser.add_argument(
        "-u",
        "--update-config",
        help="Update local config settings with the additional ones found in the template and exit. Copy blendcfg.yaml to CWD instead if there is no CWD config file found.",
        action="store_true",
    )
    parser.add_argument(
        "-l",
        "--list-objects",
        dest="list",
        help="Print Blender file object hierarchy to console, includes Objects and Collections",
        action="store_true",
    )

    return parser.parse_args()


def import_python_submodules() -> None:
    """Import all available extension Python submodules from the environment."""
    # Look in the `modules` directory under site-packages
    modules_path = os.path.join(os.path.dirname(__file__), "jobs")
    for _, module_name, _ in pkgutil.walk_packages([modules_path], prefix="pcbooth.jobs."):
        logger.debug("Importing Python submodule: %s", module_name)
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.warning("Python submodule %s failed to load!", module_name)
            logger.debug("Submodule load exception: %s", str(e))


def find_module(name: str) -> Optional[type]:
    """Find a class that matches the given module name.

    This matches a config job name, for example TRANSITIONS, to a Python
    class defined somewhere within the available Python environment.
    The class must derive from `Job` available in core/job.py.
    """
    for _, obj in inspect.getmembers(sys.modules["pcbooth.jobs"]):
        if not inspect.ismodule(obj):
            continue

        for subname, subobj in inspect.getmembers(obj):
            uppercase_name = subname.upper()
            if inspect.isclass(subobj) and issubclass(subobj, pcbooth.core.job.Job) and name == uppercase_name:
                logger.debug("Found module: %s in %s", subname, obj)
                return subobj

    return None


def create_modules(config: list[dict[Any, Any]]) -> list[pcbooth.core.job.Job]:
    """Create jobs based on the blendcfg.yaml configuration file."""
    import_python_submodules()

    runnable_modules = []
    if not config:
        logger.error(f"No rendering jobs specified in OUTPUTS")
        sys.exit(1)
    logger.debug("Execution plan:")
    for v in config:
        name, params = next(iter(v.items()))
        logger.debug("- job: %s (params: %s)", name, params)

        # Find a class that matches the module name
        class_type = find_module(name)
        if not class_type:
            raise RuntimeError(
                f"Could not find job {name} anywhere! "
                "Have you defined a class for the module, and is it a subclass of pcbooth.core.job.Job?"
            )

        # We got a type, we can now create the object
        # This is just a constructor call
        try:
            module = class_type(params)
            runnable_modules.append(module)
        except Exception as e:
            raise RuntimeError(f"Failed to create module {name}: {str(e)}") from e

    return runnable_modules


def run_modules_for_config(conf: dict[Any, Any], studio: Studio) -> None:
    """Run all module processing jobs for the specified blendcfg.yaml."""
    modules = create_modules(conf["OUTPUTS"])

    logger.info("Number of jobs to run: %d", len(modules))
    for job in modules:
        logger.debug("Running module: %s", job)
        job.execute(studio)
        logger.debug("Finished running: %s", job)


def main() -> int:
    try:
        args = parse_args()
        log.set_logging(args.debug)

        if config.init_global(args):
            cu.open_blendfile(config.pcb_blend_path)
            if args.list:
                cu.print_hierarchy()
                return 0
            studio = Studio()
            run_modules_for_config(config.blendcfg, studio)
        return 0

    except blendcfg.BlendcfgValidationError as e:
        logger.error("%s", str(e), exc_info=False)
        return 1
    except Exception as e:
        logger.error("%s", str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
