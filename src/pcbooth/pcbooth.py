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

        ###
        # st.set_space_shading("SOLID")
        if config.isPCB:  # isPCB and no components
            #    ========== process single board ==========
            # if no components are found on mesh, imports them and then saves the PCB
            config.rendered_obj = bpy.data.objects[config.PCB_name]
            board_col = bpy.data.collections.get("Board")

            st.rotate_all(config.rendered_obj)

        else:
            #    ========== process assembly/unknown file ==========
            if config.isAssembly:
                col = bpy.data.collections.get("Assembly")
            elif config.isUnknown:
                # Unknown can any blend we want to render with kbe, but most often this will be single, bare component
                # get main collection under Scene Collection
                col = bpy.context.scene.collection.children[0].objects[0]
                if len(col.objects) == 1:
                    # Make sure object is centered in scene
                    model = col.objects[0]
                    model.select_set(True)
                    bpy.context.view_layer.objects.active = model
                    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
                    model.location[:] = [0, 0, 0]
                    bpy.ops.object.transform_apply()

            bbox_mesh = cu.get_bbox_linked(col)
            # parent to empty object (pcb_parent)
            bpy.ops.object.select_all(action="DESELECT")
            for obj in col.objects:
                # if object is not a child of another object
                if obj.parent is None:
                    obj.select_set(True)
            cu.link_obj_to_collection(bbox_mesh, col)
            # active obj will be parent
            bpy.context.view_layer.objects.active = bbox_mesh
            bpy.ops.object.parent_set(keep_transform=True)
            bpy.ops.object.select_all(action="DESELECT")
            config.rendered_obj = bbox_mesh

        st.add_studio(config.rendered_obj)

        if config.blendcfg["SETTINGS"]["SAVE_SCENE"]:
            blend_scene_path = config.pcb_blend_path.replace(".blend", "_scene.blend")
            for cam_type in config.cam_types:
                cam_obj = bpy.data.objects.get(f"camera_{cam_type.lower()}")
                if cam_obj is not None:
                    st.studio_prepare(config.rendered_obj, "Transparent", cam_obj)
            # save_pcb_blend(blend_scene_path)

        if config.isAssembly and config.blendcfg["OUTPUT"]["EXPLODEDVIEW"]:
            make_explodedview(config.rendered_obj, "exploded view:")
        if (
            config.blendcfg["OUTPUT"]["HOTAREAS"]
            and not config.blendcfg["OUTPUT"]["EXPLODEDVIEW"]
        ):
            hotarea_renders(config.rendered_obj, "hotareas:")
            st.obj_set_rotation(config.rendered_obj)

        if config.blendcfg["OUTPUT"]["RENDERS"]:
            st.studio_renders(config.rendered_obj, "renders:")
            st.obj_set_rotation(config.rendered_obj)

        if config.blendcfg["OUTPUT"]["STACKUP"]:
            make_stackup(config.rendered_obj)
            st.obj_set_rotation(config.rendered_obj)

        if config.blendcfg["OUTPUT"]["ANIMATIONS"]:
            make_animations(config.rendered_obj, "animations:")
            st.obj_set_rotation(config.rendered_obj)
        if config.blendcfg["OUTPUT"]["TRANSITIONS"][0]:
            make_transitions(config.rendered_obj, "portal:")
            st.obj_set_rotation(config.rendered_obj)

    except Exception:
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
