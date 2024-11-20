import bpy
import traceback
import sys
import argparse
import logging
import pcbooth.modules.config as config
import pcbooth.modules.custom_utilities as cu
import pcbooth.modules.studio as st
import pcbooth.modules.fileIO as fio
from pcbooth.modules.animation import make_animations
from pcbooth.modules.hardware_portal import make_transitions, make_stackup
from pcbooth.modules.hotareas import hotarea_renders
from pcbooth.modules.assembly import make_explodedview
import pcbooth.core.blendcfg as blendcfg
import pcbooth.core.log as log
from os import path, getcwd


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=35)

    parser = argparse.ArgumentParser(
        prog="kbe",
        prefix_chars="-",
        formatter_class=formatter,
        description="kbe - script used to provide PCB 3D models and renders from PCB production files. Program must be run in project workdir.",
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
        "-g",
        "--get-config",
        help="Copy blendcfg.yaml to CWD and exit",
        action="store_true",
    )

    return parser.parse_args()


def main():
    try:
        args = parse_args()
        log.set_logging(args.debug)

        if args.get_config:
            prj_path = getcwd() + "/"
            pcbt_dir_path = path.dirname(__file__)
            blendcfg.check_and_copy_blendcfg(prj_path, pcbt_dir_path, force=True)
            return 0

        config.init_global(args)
        cu.save_pcb_blend("test.blend")

    except Exception:
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
