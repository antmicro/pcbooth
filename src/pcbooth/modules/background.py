import bpy
import pcbooth.modules.config as config
from math import pi
from mathutils import Matrix, Euler
import pcbooth.modules.fileIO as fio
import logging

logger = logging.getLogger(__name__)


def load_env_texture():
    logger.debug("Loading environmental texture")
    fio.import_from_blendfile(config.mat_blend_path, "worlds")
    bpy.context.scene.world = bpy.data.worlds["Studio"]
    for world in bpy.data.worlds:
        if "World" in world.name:
            bpy.data.worlds.remove(bpy.data.worlds[world.name])
    node_tree = bpy.data.worlds["Studio"].node_tree
    bpy.data.images[config.env_texture_name].filepath = config.env_texture_path
    hdrimap = node_tree.nodes["Mapping"]
    hdrimap.inputs[2].default_value[0] = -pi / 6
    hdrimap.inputs[2].default_value[1] = 0
    hdrimap.inputs[2].default_value[2] = pi / 2

    out = node_tree.nodes["World Output"]
    hdribg = node_tree.nodes["Background"]
    hdribg.inputs[1].default_value = 0.1

    ambient = node_tree.nodes.new("ShaderNodeBackground")
    ambient.inputs[0].default_value = [0.75, 0.75, 0.7, 1.0]

    mix = node_tree.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.1

    # link nodes
    links = node_tree.links
    links.remove(out.inputs[0].links[0])
    links.new(hdribg.outputs[0], mix.inputs[1])
    links.new(ambient.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs[0])
    links = node_tree.links


def update_env_texture(cam_obj):  # rotate env texture to match camera angle
    rx, ry, rz = cam_obj.rotation_euler
    # rotation
    bpy.data.worlds["Studio"].node_tree.nodes["Mapping"].inputs[2].default_value[0] = (
        pi / 3
    ) - rx
    bpy.data.worlds["Studio"].node_tree.nodes["Mapping"].inputs[2].default_value[
        1
    ] = -ry
    bpy.data.worlds["Studio"].node_tree.nodes["Mapping"].inputs[2].default_value[2] = (
        pi - rz
    )
    # # scale
    # bpy.data.worlds["Studio"].node_tree.nodes["Mapping"].inputs[3].default_value[0] = -1 if (cam_obj.scale.x < 0) else 1
    # bpy.data.worlds["Studio"].node_tree.nodes["Mapping"].inputs[3].default_value[1] = -1 if (cam_obj.scale.y < 0) else 1
    # bpy.data.worlds["Studio"].node_tree.nodes["Mapping"].inputs[3].default_value[2] = -1 if (cam_obj.scale.z < 0) else 1


def add_background(pcb_parent, bg_name, bg_file_path):
    logger.debug("Loading background files")
    backgroundCol = fio.import_from_blendfile(bg_file_path, "collections")[0]
    backgroundCol.name = "Background_" + bg_name
    for obj in backgroundCol.objects:
        obj["default_loc"] = obj.location  # save each object's default location

    backgroundCol.hide_render = True
    backgroundCol.hide_viewport = True
    return backgroundCol


def reset_background_location(background):
    for background_obj in background.objects:
        background_obj.location = background_obj["default_loc"]


# move and rotate background + change material
def update_background(object_parent, backgroundCol, cam_obj):
    # transformation matrix
    obj_transform_matrix = Matrix.LocRotScale(
        object_parent.location, Euler(object_parent.rotation_euler), object_parent.scale
    )
    # find object's vertex that will touch background base (is lowest)
    object_min_Z = 100
    for vert in object_parent.data.vertices:  # check all object's vertices
        height_Z = (obj_transform_matrix @ vert.co)[2]
        if height_Z < object_min_Z:
            object_min_Z = height_Z

    # if object is pcbooth.s PCB - check also for components, not needed for assemblies
    # as they use entire-model bounding box as parent
    if config.isPCB:
        # then check all PCB's components vertices
        for obj in bpy.data.collections.get("Components").objects:
            if "Annotations" in obj.name:
                continue
            # vertices are saved before any transformation!
            for vert in obj.data.vertices:
                # apply obj scale
                comp_transform_matrix = Matrix.LocRotScale(
                    obj.location,
                    Euler(obj.rotation_euler),
                    obj.scale,
                )
                height_Z = (obj_transform_matrix @ comp_transform_matrix @ vert.co)[2]
                if height_Z < object_min_Z:
                    object_min_Z = height_Z

    # move to default position
    reset_background_location(backgroundCol)

    # for each object in the background
    for background in backgroundCol.objects:
        # apply background's Z location to object position
        background.location[2] += object_min_Z  # distance should be negative!
        background.location[2] -= 0.05  # slight offset


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
