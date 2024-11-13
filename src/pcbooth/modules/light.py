import bpy
import pcbooth.modules.custom_utilities as cu
import pcbooth.modules.config as config
from math import pi, atan
from mathutils import Vector
import math


def helper_find_rotation(pos, look_pos):
    v = -(Vector(look_pos) - Vector(pos)).normalized()
    x = atan(v[2] / v[1]) - pi / 2
    y = atan(v[2] / v[0])
    y = (pi / 2 if y > 0 else -pi / 2) - y
    z = 0  # atan(v[0]/v[1])
    return (x, y, z)


def check_numbers(source_numbers: list, target_values: list) -> list:
    """
    Checks if every number from source_numbers match value from target_values

    If target value is greater or equal zero:
      If source number is lower than target value, value of the source number
      will be changed to target value, otherwise source value will be left
      unchanged
    If target value is lower than zero:
      If source number is greater than target value, value of the source number
      will be changed to target value, otherwise source value will be left
      unchanged

    Parameters:
      source_numbers (list): list of numbers to check
      target_values (list): list of target values

    Returns:
      source_numbers (touple): modified version of the `source_numbers`
    """

    for idx in range(0, len(source_numbers)):
        if target_values[idx] >= 0:
            if source_numbers[idx] < target_values[idx]:
                source_numbers[idx] = target_values[idx]
        else:
            if source_numbers[idx] > target_values[idx]:
                source_numbers[idx] = target_values[idx]

    return tuple(source_numbers)


def add_light(pcb_parent):  # used to setup lights for render
    scale_multiplier = 300  # influences size of the area lights added to scene
    position_multiplier = 1.5  # influences distance between the lights and object

    lightCol = bpy.data.collections.new("light")

    color = config.blendcfg["EFFECTS"]["LIGHTS_COLOR"]
    energy = float(config.blendcfg["EFFECTS"]["LIGHTS_INTENSITY"])

    min_x = -pcb_parent.dimensions.x / 2
    max_x = pcb_parent.dimensions.x / 2
    min_y = -pcb_parent.dimensions.y / 2
    max_y = pcb_parent.dimensions.y / 2
    # default values found for board with size 70x55x1.6
    # scales default values depending on difference in size of PCB
    x_scale = pcb_parent.dimensions.x / 70
    y_scale = pcb_parent.dimensions.y / 55
    max_scale = max(x_scale, y_scale)
    if max_scale < 1:
        max_scale = 1

    z_offset = round(
        math.sqrt(pcb_parent.dimensions.x / 70 * pcb_parent.dimensions.y / 55)
    )
    if z_offset < 1:
        z_offset = 1

    right_light = Light("Right_light", "AREA", color, energy * max_scale**1.2)
    right_pos = [max_x * 3 / 4, max_y * 1 / 5, 45 * z_offset]
    right_pos = check_numbers(
        right_pos,
        [28 * position_multiplier, 5 * position_multiplier, 45 * position_multiplier],
    )
    right_look_pos = (max_x * 9 / 14, min_y * 1 / 5, 0)
    right_scale = (scale_multiplier * x_scale, scale_multiplier * y_scale, 1)
    right_light.set_transformation(
        right_pos, helper_find_rotation(right_pos, right_look_pos), right_scale
    )

    left_light = Light("Left_light", "AREA", color, energy * max_scale**1.2)
    left_pos = [min_x * 5 / 6, max_y * 2 / 5, 55 * z_offset]
    left_pos = check_numbers(
        left_pos,
        [-31 * position_multiplier, 10 * position_multiplier, 55 * position_multiplier],
    )
    left_look_pos = (min_x * 1 / 2, min_y * 1 / 5, 0)
    left_scale = (scale_multiplier * x_scale, scale_multiplier * y_scale, 1)
    left_light.set_transformation(
        left_pos, helper_find_rotation(left_pos, left_look_pos), left_scale
    )

    top_light = Light("Top_light", "AREA", color, energy * max_scale**1.2)
    top_pos = [min_x * 1 / 4, max_y * 3 / 2, 50 * z_offset]
    top_pos = check_numbers(
        top_pos,
        [-10 * position_multiplier, 37 * position_multiplier, 50 * position_multiplier],
    )
    top_look_pos = (max_x * 1 / 3, max_y, 0)
    top_scale = (scale_multiplier * x_scale, scale_multiplier * y_scale, 1)
    top_light.set_transformation(
        top_pos, helper_find_rotation(top_pos, top_look_pos), top_scale
    )

    # lights for stackup view
    # set area light below and above each layer (and parent to layer)
    layer_light_area = pcb_parent.dimensions.x * pcb_parent.dimensions.y
    layer_light_scale = layer_light_area / (70**2)
    layer_light_power = 1000 * layer_light_scale
    layer_light_epsilon = Vector((0, 0, 0.001))

    # for name PCB_layerN (N=number) skip 'PCB_layer', sort by int(N)
    if config.isPCB:
        layers = [child for child in pcb_parent.children if "PCB_layer" in child.name]
        sorted_layers = sorted(layers, key=lambda x: int(x.name[9:]))
    else:
        sorted_layers = [pcb_parent]
    bpy.ops.object.select_all(action="DESELECT")
    lightCol = bpy.data.collections.get("light")

    cumulative_PCB_width = Vector((0, 0, 0))
    for layer in sorted_layers[:-1]:  # layer top light, without top layer
        layer_light = Light(
            layer.name + "_light_top", "AREA", color, layer_light_power
        ).obj
        layer_light.data.shape = "RECTANGLE"
        layer_light.data.size = pcb_parent.dimensions.x
        layer_light.data.size_y = pcb_parent.dimensions.y
        layer_light.location = (
            layer.location
            + Vector((0, 0, layer.dimensions[2]))
            + cumulative_PCB_width
            + layer_light_epsilon
        )
        cumulative_PCB_width += Vector((0, 0, layer.dimensions[2]))
        layer.select_set(True)
        layer_light.select_set(True)
        bpy.context.view_layer.objects.active = layer  # active obj will be parent
        bpy.ops.object.parent_set(keep_transform=True)
        bpy.ops.object.select_all(action="DESELECT")

    cumulative_PCB_width = Vector((0, 0, sorted_layers[0].dimensions[2]))
    for layer in sorted_layers[1:]:  # layer bottom light, without bottom layer
        layer_light = Light(
            layer.name + "_light_bot", "AREA", color, layer_light_power
        ).obj
        layer_light.data.shape = "RECTANGLE"
        layer_light.data.size = pcb_parent.dimensions.x
        layer_light.data.size_y = pcb_parent.dimensions.y
        layer_light.rotation_euler[1] = 3.14159  # rotate by 180d
        layer_light.location = (
            layer.location + cumulative_PCB_width - layer_light_epsilon
        )
        cumulative_PCB_width += Vector((0, 0, layer.dimensions[2]))
        layer.select_set(True)
        layer_light.select_set(True)
        bpy.context.view_layer.objects.active = layer  # active obj will be parent
        bpy.ops.object.parent_set(keep_transform=True)
        bpy.ops.object.select_all(action="DESELECT")

    for light_class in config.all_light_objects:
        obj = light_class.obj
        cu.link_obj_to_collection(obj, lightCol)

    return lightCol


class Light:  # generic class for light objects
    def __init__(self, Name, Type, color, energy):
        self.name = Name
        self.light = bpy.data.lights.new(name=Name, type=Type)
        self.light.energy = energy

        self.obj = bpy.data.objects.new(name=Name, object_data=self.light)
        bpy.context.collection.objects.link(self.obj)
        self.obj.data.color = color
        config.all_light_objects.append(self)

    def set_transformation(self, loc=(0, 0, 0), rot=(0, 0, 0), sca=(1, 1, 1)):
        self.obj.location = loc
        self.obj.rotation_euler = rot
        self.obj.scale = sca


# blender requirement, usefull for API additions
def register():
    pass


def unregister():
    pass


if __name__ == "__main__":
    register()
