import bpy
import pcbooth.core.job
from pcbooth.modules.camera import Camera
from pcbooth.modules.background import Background
from pcbooth.modules.renderer import RendererWrapper
import pcbooth.modules.custom_utilities as cu
import pcbooth.modules.job_utilities as ju
import logging

from typing import Tuple, Set

logger = logging.getLogger(__name__)

HIGHLIGHTED = ["J", "SW"]
HIDDEN = ["R", "C", "T", "Q", "FB"]

WHITE_RGB = "FFFFFF"
HIGHLIGHT_RGB = "004C3C"


class Highlights(pcbooth.core.job.Job):
    """
    Highlighted components images rendering job.

    This module handles rendering static images of a model with simplified
    color pallette and its components highlighted using contrasting color.
    This can be used to provide images for hardware documentation, to pinpoint
    specific components.

    Yields renders to <RENDER_DIR>/highlights/ directory. Filename is determined based on model type:
        * for PCBs, designator of the rendered component is used as name (adds <camera> suffix if camera is other than "TOP")
        * for other types of model, full rendered object name is used with <camera><position initial> suffix

    Warning: Additional linked objects' materials won't be overridden - they will be hidden for rendering!
    """

    def _override_studio(self) -> None:
        if background := Background.get("transparent"):
            self.studio.backgrounds = [background]
        self.studio.positions = ["TOP", "BOTTOM"]

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        renderer = RendererWrapper()

        highlighted, hidden = self.get_component_lists()
        total_renders = len(highlighted) * len(self.studio.cameras) * (1 if self.studio.is_pcb else 2)
        self.update_status(total_renders)
        Background.use(self.studio.backgrounds[0])
        object = self.studio.top_parent
        white_mat = add_material("white", WHITE_RGB)
        highlight_mat = add_material("highlight", HIGHLIGHT_RGB)

        with ju.hide_override(hidden), ju.material_override(white_mat, list(bpy.data.objects)):
            for camera in self.studio.cameras:
                for component in highlighted:
                    with ju.material_override(highlight_mat, [component]):
                        if component in self.studio.top_components:
                            self.render_side("TOP", component, object, camera, renderer)

                        if component in self.studio.bottom_components:
                            self.render_side("BOTTOM", component, object, camera, renderer)

    def render_side(
        self,
        side: str,
        component: bpy.types.Object,
        target: bpy.types.Object,
        camera: Camera,
        renderer: RendererWrapper,
    ) -> None:
        """Rendering functions to be called for each side."""
        filename = self.get_name(component, side, camera)
        self.studio.change_position(side)
        Background.update_position(target)
        camera.change_position(side)
        renderer.render(camera.object, filename)
        renderer.clear_cache()
        self.update_status()

    def get_component_lists(
        self,
    ) -> Tuple[Set[bpy.types.Object], Set[bpy.types.Object]]:
        """
        Get list of components to highlight (HIGHLIGHTED list of designators or all components present if not PCB) and
        list of components to hide (HIDDEN list of designators and all linked objects).
        """

        rendered = set(dict.fromkeys(self.studio.top_components + self.studio.bottom_components))
        linked = {object for object in cu.get_linked() if not is_background(object)}
        hidden = {component for component in rendered if is_hidden(component, self.studio.is_pcb)} | linked
        highlighted = {component for component in rendered if is_highlighted(component, self.studio.is_pcb)} - hidden

        if self.studio.is_pcb:  # hide PCB model solder object if present
            if solder := bpy.data.objects.get("Solder", None):
                hidden.add(solder)

        if not highlighted:
            logger.warning("No highlighted components found!")
        return highlighted, hidden

    def get_name(self, object: bpy.types.Object, position: str, camera: Camera) -> str:
        """Get object name or designator, depends on model type (designator if model is a PCB, object name if other)"""
        prefix = f"highlights/"
        suffix = f"_{camera.name.lower()}" if camera.name != "TOP" else ""
        if self.studio.is_pcb:
            designator = cu.get_designator(object)
            return f"{prefix}{designator}{suffix}"
        return f"{prefix}{object.name}{suffix}{position[0]}"


def is_highlighted(object: bpy.types.Object, is_pcb: bool = True) -> bool:
    """
    Check if component is supposed to be highlighted.
    Compares with HIGHLIGHTED list of designators.
    If model is not PCB type, always returns True.
    """
    if not is_pcb:
        return True
    designator = cu.get_designator(object)
    return any(designator.startswith(des) for des in HIGHLIGHTED)


def is_background(object: bpy.types.Object) -> bool:
    """
    Check if component is Studio background.
    """
    return object.users_collection[0] == Background.collection


def is_hidden(object: bpy.types.Object, is_pcb: bool = True) -> bool:
    """
    Check if component is supposed to be hidden.
    Compares with HIDDEN list of designators.
    If model is not PCB type, always returns False.
    """
    if not is_pcb:
        return False
    designator = cu.get_designator(object)
    return any(designator.startswith(des) for des in HIDDEN)


def add_material(name: str, rgb: str) -> bpy.types.Material:
    """Add simple BSDF material of specified name and RGB color."""
    rgba = cu.hex_to_rgb(rgb) + (1.0,)
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = rgba  # type: ignore
    return material


def set_material(object: bpy.types.Object, material: bpy.types.Material) -> None:
    """Sets provided material in all material slots of an object."""
    for slot in object.material_slots:
        slot.material = material
