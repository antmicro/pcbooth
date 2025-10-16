"""Module containing utility functions for rendering jobs."""

from typing import Generator, List, Callable, Optional, Any, Set
import bpy
from contextlib import contextmanager
from pcbooth.modules.renderer import (
    restore_default_cycles,
    set_default_compositing,
)
from pcbooth.modules.light import Light
from pcbooth.modules.background import Background
from pcbooth.modules.studio import Studio
from mathutils import Vector, Euler
import logging

logger = logging.getLogger(__name__)


@contextmanager
def holdout_override(
    components: List[bpy.types.Object] | Set[bpy.types.Object],
    full: bool = False,
) -> Generator[None, Any, None]:
    """Apply holdout override for components from provided list. If non_obstructed"""
    try:
        if full:
            for component in bpy.data.objects:
                if component.library:
                    continue
                component.hide_render = True
        for component in components:
            component.is_holdout = True
            component.hide_render = False
        yield
    except AttributeError:
        pass
    finally:
        for component in bpy.data.objects:
            if component.library:
                continue
            component.hide_render = False
        for component in components:
            if component.library:
                continue
            component.is_holdout = False


@contextmanager
def hide_override(
    components: List[bpy.types.Object] | Set[bpy.types.Object],
    hide_viewport: bool = False,
) -> Generator[None, Any, None]:
    """Apply hide from render override for components from provided list."""
    try:
        for component in components:
            component.hide_render = True
            if hide_viewport:
                component.hide_viewport = True
        yield
    except AttributeError:
        pass
    finally:
        for component in components:
            component.hide_render = False
            component.hide_viewport = False


@contextmanager
def global_material_override(
    base_material: Optional[bpy.types.Material] = None,
) -> Generator[None, Any, None]:
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
        bpy.context.view_layer.material_override = None  # type: ignore


@contextmanager
def material_override(
    base_material: bpy.types.Material,
    components: List[bpy.types.Object] | Set[bpy.types.Object],
) -> Generator[None, Any, None]:
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
            if hasattr(component.data, "materials") and len(component.material_slots) == 0:
                component.data.materials.append(base_material)
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
            if hasattr(component.data, "materials") and len(materials) == 0:
                component.data.materials.clear()
                continue
            for i in range(len(materials)):
                component.material_slots[i].material = materials[i]


@contextmanager
def compositing_override(compositing_func: Callable[..., None]) -> Generator[None, Any, None]:
    """Apply compositor override."""
    try:
        compositing_func()
        yield
    except (AttributeError, RuntimeError):
        pass
    finally:
        set_default_compositing()


@contextmanager
def cycles_override(settings_func: Callable[..., None]) -> Generator[None, Any, None]:
    """Apply Cycles settings override."""
    try:
        settings_func()
        yield
    except (AttributeError, RuntimeError):
        pass
    finally:
        restore_default_cycles()


@contextmanager
def shadow_override(
    components: List[bpy.types.Object] | Set[bpy.types.Object],
) -> Generator[None, Any, None]:
    """Override object visibility to shadow rays."""
    try:
        for component in components:
            component.visible_shadow = False
        yield
    except AttributeError:
        pass
    finally:
        for component in components:
            component.visible_shadow = True


@contextmanager
def position_override(
    components: List[bpy.types.Object] | Set[bpy.types.Object],
    position_func: Callable[[List[bpy.types.Object]], None],
    rendered_obj: Optional[bpy.types.Object] = None,
) -> Generator[None, Any, None]:
    """
    Temporarily change location or rotation of components from provided list by updating their delta location and Euler rotation. Uses function passed as argument.
    Restore original location and rotation in the end. By passing rendered object to the context manager,
    light will be adjusted to the updated model position as well.
    """
    try:
        position_func(list(components))
        if rendered_obj:
            Light.update(rendered_obj)
            Background.update_position(rendered_obj)
        yield
    except AttributeError:
        pass
    finally:
        for component in components:
            component.delta_location = Vector((0, 0, 0))  # type: ignore
            component.delta_rotation_euler = Euler((0, 0, 0))  # type: ignore
        if rendered_obj:
            Light.update(rendered_obj)
            Background.update_position(rendered_obj)


@contextmanager
def user_animation_override(studio: Studio) -> Generator[None, Any, None]:
    """
    Temporarily override PCBooth animations with user-defined keyframes from the rendered .blend file.
    Removes any changes made within this context upon exit.
    """
    try:
        studio.set_frames()
        for bl_id, data in studio.animation_data.items():
            if not data:
                continue
            bl_id.animation_data_create()
            bl_id.animation_data.action = data.original  # type: ignore
        yield

    finally:
        studio.clear_animation_data()
