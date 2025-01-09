"""Module containing utility functions for rendering jobs."""

from typing import List, Callable, Optional
import bpy
from contextlib import contextmanager
from pcbooth.modules.renderer import (
    restore_default_cycles,
    set_default_compositing,
)


@contextmanager
def holdout_override(components: List[bpy.types.Object], unobstructed: bool = False):
    """Apply holdout override for components from provided list. If non_obstructed"""
    try:
        if unobstructed:
            for component in bpy.data.objects:
                component.hide_render = True
        for component in components:
            component.is_holdout = True
            component.hide_render = False
        yield
    except AttributeError:
        pass
    finally:
        for component in bpy.data.objects:
            component.hide_render = False
        for component in components:
            component.is_holdout = False


@contextmanager
def hide_override(components: List[bpy.types.Object]):
    """Apply hide from render override for components from provided list."""
    try:
        for component in components:
            component.hide_render = True
        yield
    except AttributeError:
        pass
    finally:
        for component in components:
            component.hide_render = False


@contextmanager
def global_material_override(base_material: Optional[bpy.types.Material] = None):
    """Apply global material override for all objects in a scene."""
    try:
        if base_material:
            override_material = base_material
        else:
            if override_material := bpy.data.materials.get("_override"):
                pass
            else:
                override_material = bpy.data.materials.new("_override")
        bpy.context.view_layer.material_override = override_material
        yield
    except (AttributeError, RuntimeError):
        pass
    finally:
        bpy.context.view_layer.material_override = None


@contextmanager
def material_override(
    base_material: bpy.types.Material,
    components: List[bpy.types.Object],
):
    """
    Override all materials with the specified one for all components in the list.
    Skips linked objects. Generates backup dictionary with the material slots for revert.
    """
    try:
        backup = {}
        for component in components:
            backup[component] = [slot.material for slot in component.material_slots]
        for component in backup.keys():
            if component.library:
                continue
            for slot in component.material_slots:
                slot.material = base_material
        yield
    except AttributeError:
        pass
    finally:
        """Revert material data from backup dictionary."""
        for component, materials in backup.items():
            if component.library:
                continue
            for i in range(len(materials)):
                component.material_slots[i].material = materials[i]


@contextmanager
def compositing_override(compositing_func: Callable):
    """Apply compositor override."""
    try:
        compositing_func()
        yield
    except (AttributeError, RuntimeError):
        pass
    finally:
        set_default_compositing()


@contextmanager
def cycles_override(settings_func: Callable):
    """Apply Cycles settings override."""
    try:
        settings_func()
        yield
    except (AttributeError, RuntimeError):
        pass
    finally:
        restore_default_cycles()
