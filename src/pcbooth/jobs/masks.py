import bpy
import pcbooth.core.job
from pcbooth.modules.camera import Camera
from pcbooth.modules.background import Background
from pcbooth.modules.renderer import (
    RendererWrapper,
    set_lqbw_compositing,
    setup_ultralow_cycles,
)
import pcbooth.modules.job_utilities as ju
import pcbooth.modules.custom_utilities as cu
import logging
from typing import Set, List
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class Masks(pcbooth.core.job.Job):
    """
    Component binary masks rendering job.

    This module handles fast rendering of static images of each model's component using black and white color
    pallette. These images can act as binary masks, enabling precise identification of the component's location
    within a full-color render. Masks are rendered for each camera in each model position specified in config.

    Yields renders to <RENDER_DIR>/masks/<full/covered>/<camera name><position initial>/ directory. Filename is determined based
    on model type:
        * for PCBs, designator of the rendered component is used as name
        * for other types of model, full rendered object name is used
    """

    class ParameterSchema(BaseModel):
        """
        Pydantic schema class for optional job parameters.
        Overwrite this in deriving classes to add their own parameters.
        """

        FULL: bool = False
        COVERED: bool = True
        HIGHLIGHTED: List[str] = ["A", "J", "PS", "T", "U", "IC", "POT"]

    def _override_studio(self) -> None:
        self.studio.positions = ["TOP", "BOTTOM"]

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        if not self.params.get("FULL") and not self.params.get("COVERED"):
            logger.warning(
                "All subtypes of masks are disabled, nothing to render within this job."
            )
            return

        renderer = RendererWrapper()
        object = self.studio.top_parent
        highlighted = self.get_component_lists()
        len_params = sum(value is True for value in self.params.values())
        total_renders = (
            len(highlighted)
            * len(self.studio.cameras)
            * (1 if self.studio.is_pcb else 2)
            * len_params
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
                        if self.params.get("FULL"):
                            self.render_side(component, object, camera, renderer, True)
                        if self.params.get("COVERED"):
                            self.render_side(component, object, camera, renderer, False)

    def render_side(
        self,
        component: bpy.types.Object,
        target: bpy.types.Object,
        camera: Camera,
        renderer: RendererWrapper,
        full: bool,
    ) -> None:
        """Rendering functions called regardless of position."""
        with ju.holdout_override([component], full=full):
            for side, components in [
                ("TOP", self.studio.top_components),
                ("BOTTOM", self.studio.bottom_components),
            ]:
                if full:
                    state = "full"
                else:
                    state = "covered"

                if component in components:
                    filename = self.get_name(component, side, camera, state)
                    self.studio.change_position(side)
                    Background.update_position(target)
                    camera.change_position(side)
                    renderer.render(camera.object, filename)
                    renderer.clear_cache()
                    self.update_status()

    def get_component_lists(self) -> Set[bpy.types.Object]:
        """
        Get list of components to highlight (HIGHLIGHTED list of designators or all components present if not PCB).
        """
        rendered = set(
            dict.fromkeys(self.studio.top_components + self.studio.bottom_components)
        )
        highlighted = {
            component
            for component in rendered
            if self.is_highlighted(component, self.studio.is_pcb)
        }
        if not highlighted:
            logger.warning("No highlighted components found!")
        return highlighted

    def get_name(
        self, object: bpy.types.Object, position: str, camera: Camera, state: str
    ) -> str:
        """Get object name or designator, depends on model type (designator if model is a PCB, object name if other)"""
        prefix = f"masks/{state}/{camera.name.lower()}{position[0]}/"
        if self.studio.is_pcb:
            designator = cu.get_designator(object)
            return f"{prefix}{designator}"
        return f"{prefix}{object.name}"

    def is_highlighted(self, object: bpy.types.Object, is_pcb: bool = True) -> bool:
        """
        Check if component is supposed to be highlighted.
        Compares with HIGHLIGHTED list of designators.
        If model is not PCB type, always returns True.
        """
        if not is_pcb:
            return True
        designator = cu.get_designator(object)
        if highlighted := self.params.get("HIGHLIGHTED"):
            return any(designator.startswith(des) for des in highlighted)
        return False
