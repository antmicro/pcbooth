import bpy
from pcbooth.core.job import UserAnimationJob
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


logger = logging.getLogger(__name__)


class Masks(UserAnimationJob):
    """
    Component binary masks rendering job.

    This module handles fast rendering of static images of each model's component using black and white color
    pallette. These images can act as binary masks, enabling precise identification of the component's location
    within a full-color render. Masks are rendered for each camera in each model position specified in config.
    Rendering selected frames from user-predefined animation data is supported.

    Yields renders to <RENDER_DIR>/masks/<full/covered>/<camera name><position initial>/ directory. Filename is determined based
    on model type:
        * for PCBs, designator of the rendered component is used as name
        * for other types of model, full rendered object name is used
    """

    class ParameterSchema(UserAnimationJob.ParameterSchema):
        """
        Pydantic schema class for optional job parameters.
        Overwrite this in deriving classes to add their own parameters.
        """

        FULL: bool = False
        COVERED: bool = True
        HIGHLIGHTED: List[str] = ["A", "J", "PS", "T", "U", "IC", "POT"]

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        if not self.params.get("FULL") and not self.params.get("COVERED"):
            logger.warning("All subtypes of masks are disabled, nothing to render within this job.")
            return

        renderer = RendererWrapper()
        highlighted = self.get_component_lists()
        len_params = sum(value is True for value in self.params.values())
        total_renders = (
            len(highlighted) * len(self.studio.cameras) * len(self.studio.positions) * len_params * len(self.frames)
        )
        self.update_status(total_renders)
        with (
            ju.cycles_override(setup_ultralow_cycles),
            ju.compositing_override(set_lqbw_compositing),
            ju.global_material_override(),
        ):
            for position in self.studio.positions:
                self.studio.change_position(position)
                Background.update_position(self.studio.top_parent)

                for camera in self.studio.cameras:
                    camera.change_position(position)

                    if self.has_animation_data:
                        self.studio.add_studio_keyframes(camera)

                    with camera.dof_override():
                        for frame in self.frames:
                            bpy.context.scene.frame_set(frame)

                            for component in highlighted:
                                if (
                                    (component in self.studio.top_components and position != "TOP")
                                    or (component in self.studio.bottom_components and position != "BOTTOM")
                                    and self.studio.is_pcb
                                ):
                                    continue

                                if self.params.get("FULL"):
                                    self.render_side(position, component, camera, renderer, "full")
                                if self.params.get("COVERED"):
                                    self.render_side(position, component, camera, renderer, "covered")

    def render_side(
        self,
        side: str,
        component: bpy.types.Object,
        camera: Camera,
        renderer: RendererWrapper,
        state: str,
    ) -> None:
        """Rendering functions called regardless of position."""
        with ju.holdout_override([component], full=state == "full"):
            filename = self.get_name(component, side, camera, state)
            renderer.render(camera.object, filename)
            renderer.clear_cache()
            self.update_status()

    def get_component_lists(self) -> Set[bpy.types.Object]:
        """
        Get list of components to highlight (HIGHLIGHTED list of designators or all components present if not PCB).
        """
        rendered = set(dict.fromkeys(self.studio.top_components + self.studio.bottom_components))
        highlighted = {component for component in rendered if self.is_highlighted(component, self.studio.is_pcb)}
        if not highlighted:
            logger.warning("No highlighted components found!")
        return highlighted

    def get_name(self, object: bpy.types.Object, position: str, camera: Camera, state: str) -> str:
        """Get object name or designator, depends on model type (designator if model is a PCB, object name if other)"""
        frame = bpy.context.scene.frame_current
        prefix = (
            f"masks/{state}/{camera.name.lower()}{position[0]}/" + self.get_frame_suffix(frame).replace("_", "") + "/"
        )
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
