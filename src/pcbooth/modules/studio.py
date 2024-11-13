from typing import Literal
import bpy
import pcbooth.modules.renderer as renderer
import pcbooth.modules.config as config
from pcbooth.modules.camera import add_cameras, update_all_camera_location
from pcbooth.modules.light import add_light
from pcbooth.modules.background import (
    add_background,
    update_background,
    load_env_texture,
    reset_background_location,
)
from math import radians
from mathutils import Vector, Matrix
import logging
from pcbooth.modules.custom_utilities import apply_all_transform_obj

logger = logging.getLogger(__name__)


def rotate_all(pcb_parent):
    if pcb_parent.dimensions.x < pcb_parent.dimensions.y:
        logger.info("Rotating the PCB horizontally.")
        pcb_parent.rotation_euler.z -= radians(90)
        apply_all_transform_obj(pcb_parent)
        # rotate camera_custom object if present
        cam_obj = bpy.data.objects.get("camera_custom")
        if cam_obj is not None:
            logger.info("Rotating 'camera_custom' to follow PCB")
            cam_obj.rotation_euler.z -= radians(90)
            cam_obj.location.x, cam_obj.location.y = (
                cam_obj.location.y,
                -cam_obj.location.x,
            )


def add_studio(pcb_parent):
    renderer.init_setup()
    studioCol = bpy.data.collections.new("Studio")
    bpy.context.scene.collection.children.link(studioCol)
    studioCol.children.link(add_cameras(pcb_parent))
    studioCol.children.link(add_light(pcb_parent))
    for bg in config.blendcfg["EFFECTS"]["BACKGROUND"]:
        if bg != "Transparent":
            studioCol.children.link(
                add_background(
                    pcb_parent, bg, config.blendcfg["EFFECTS"]["BACKGROUND"][bg]
                )
            )
    load_env_texture()
    # transparent background/environmental texture
    bpy.context.scene.render.film_transparent = True
    # if custom camera present in file, ensure it has a proper focal length
    cam_obj = bpy.data.objects.get("camera_custom")
    if cam_obj is not None:
        cam_obj.data.lens = 105
        cam_obj.data.clip_start = 0.1
        cam_obj.data.clip_end = 15000
    return studioCol


def set_space_shading(Type):
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = Type


def obj_set_rotation(
    pcb,
    direction: Literal["T", "B", "R"] = "T",
    initial_rot: Vector | None = None,
):
    presets = {
        "T": (radians(0), radians(0), radians(0)),
        "B": (radians(0), radians(180), radians(0)),
        "R": (radians(0), radians(0), radians(180)),
    }
    pcb.rotation_mode = "XYZ"
    if initial_rot:
        pcb.rotation_euler = initial_rot + Vector(presets[direction])
    else:
        pcb.rotation_euler = Vector(presets[direction])
    update_all_camera_location(pcb)


def studio_prepare(pcb_parent, background, cam_obj):
    update_all_camera_location(pcb_parent)
    if not isinstance(background, str):
        update_background(pcb_parent, background, cam_obj)
    # update_env_texture(cam_obj)


# set_modifiers_visibility helper function
def set_object_mod_vis(obj, show_modifier):
    for mod in obj.modifiers:
        mod.show_in_editmode = show_modifier
        mod.show_render = show_modifier
        mod.show_viewport = show_modifier
    # obj.modifiers.remove(mod) # to delete modifier


def set_all_modifiers_visibility(pcb_parent, show_modifiers):
    logger.debug("Setting modifiers visibility to: " + str(show_modifiers))
    set_object_mod_vis(pcb_parent, show_modifiers)
    if "Components" not in bpy.data.collections:
        return
    for obj in bpy.data.collections.get("Components").objects:
        if "Annotations" not in obj.name:
            set_object_mod_vis(obj, show_modifiers)


# engine in ['WIREFRAME'/'BLENDER_WORKBENCH','BLENDER_EEVEE','CYCLES']
def studio_renders(pcb_parent, add_info=""):
    logger.info("** [RENDER] **")
    # show modifiers only when photorealistic render
    set_all_modifiers_visibility(pcb_parent, True)

    if config.blendcfg["OUTPUT"]["FREESTYLE"]:
        renderer.set_freestyle()

    direction = ["TOP", "BOTTOM", "REAR"]
    # for each background
    for bg in config.blendcfg["EFFECTS"]["BACKGROUND"]:
        if bg == "Transparent":
            backgroundCol = ""
        else:
            backgroundCol = bpy.data.collections["Background_" + bg]
            backgroundCol.hide_render = False
            backgroundCol.hide_viewport = False
        # check each direction
        for dir in direction:
            # if direction is to be rendered
            if config.blendcfg["RENDERS"][dir]:
                # check each camera type
                for cam_type in config.cam_types:
                    # if given camera is to be rendered
                    if config.blendcfg["RENDERS"][cam_type]:
                        logger.info(f"{add_info} {bg} {dir} {cam_type}")
                        file_name = (
                            config.renders_path
                            + config.PCB_name
                            + "_"
                            + dir.lower()
                            + "_"
                            + cam_type.lower()
                            + "_"
                            + bg.lower()
                        )
                        cam_obj = bpy.data.objects.get("camera_" + cam_type.lower())
                        if cam_obj is None:
                            logger.warning(
                                f"{cam_type} view enabled in config but no 'camera_{cam_type.lower()}' object found in file. Skipping render."
                            )
                        else:
                            obj_set_rotation(pcb_parent, dir[0])
                            studio_prepare(pcb_parent, backgroundCol, cam_obj)
                            renderer.render(cam_obj, file_name)
                            obj_set_rotation(pcb_parent, "T")
            if backgroundCol != "":
                reset_background_location(backgroundCol)
        if backgroundCol != "":
            backgroundCol.hide_render = True
            backgroundCol.hide_viewport = True


# changes before saving - help when opening pcb.blend in GUI
def default_world(pcb_parent):
    logger.info("Setting world to default")
    bpy.data.scenes["Scene"].display.shading.light = "STUDIO"
    bpy.context.scene.render.engine = "CYCLES"
    cam_ortho = bpy.data.objects["camera_ortho"]
    studio_prepare(pcb_parent, "Black", cam_ortho)
    set_space_shading("SOLID")


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
