import bpy
import pcbooth.core.job
from pcbooth.modules.camera import Camera
from pcbooth.modules.renderer import (
    RendererWrapper,
    set_lqbw_compositing,
    setup_ultralow_cycles,
)
import pcbooth.modules.job_utilities as ju
import pcbooth.modules.custom_utilities as cu
import logging
from typing import List

logger = logging.getLogger(__name__)

HIGHLIGHTED = ["A", "J", "PS", "T", "U", "IC", "POT"]


class Masks(pcbooth.core.job.Job):
    """
    Component binary masks rendering job.

    This module handles fast rendering of static images of each model's component using black and white color
    pallette. These images can act as binary masks, enabling precise identification of the component's location
    within a full-color render. Masks are rendered for each camera in each model position specified in config.

    Yields renders to <RENDER_DIR>/masks/<camera name><position initial>/ directory. Filename is determined based
    on model type:
        * for PCBs, designator of the rendered component is used as name
        * for other types of model, full rendered object name is used
    """

    def _override_studio(self) -> None:
        self.studio.positions = ["TOP", "BOTTOM"]

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        renderer = RendererWrapper()
        highlighted = self.get_component_lists()
        total_renders = (
            len(highlighted)
            * len(self.studio.cameras)
            * (1 if self.studio.is_pcb else 2)
        )
        self.update_status(total_renders)

        with (
            ju.cycles_override(setup_ultralow_cycles),
            ju.compositing_override(set_lqbw_compositing),
            ju.global_material_override(),
        ):
            for camera in self.studio.cameras:
                with camera.dof_override():
                    for component in highlighted:
                        with ju.holdout_override([component], unobstructed=True):
                            if component in self.studio.top_components:
                                self.render_side("TOP", component, camera, renderer)

                            if component in self.studio.bottom_components:
                                self.render_side("BOTTOM", component, camera, renderer)

    def render_side(
        self,
        side: str,
        component: bpy.types.Object,
        camera: Camera,
        renderer: RendererWrapper,
    ) -> None:
        """Rendering functions called regardless of position."""
        filename = self.get_name(component, side, camera)
        self.studio.change_position(side)
        camera.change_position(side)
        renderer.render(camera.object, filename)
        renderer.clear_cache()
        self.update_status()

    def get_component_lists(
        self,
    ) -> List[bpy.types.Object]:
        """
        Get list of components to highlight (HIGHLIGHTED list of designators or all components present if not PCB).
        """
        rendered = list(
            dict.fromkeys(self.studio.top_components + self.studio.bottom_components)
        )
        highlighted = [
            component
            for component in rendered
            if is_highlighted(component, self.studio.is_pcb)
        ]
        if not highlighted:
            logger.warning("No highlighted components found!")
        return highlighted

    def get_name(self, object: bpy.types.Object, position: str, camera: Camera) -> str:
        """Get object name or designator, depends on model type (designator if model is a PCB, object name if other)"""
        prefix = f"masks/{camera.name.lower()}{position[0]}/"
        if self.studio.is_pcb:
            designator = cu.get_designator(object)
            return f"{prefix}{designator}"
        return f"{prefix}{object.name}"


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
