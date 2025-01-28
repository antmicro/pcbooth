import bpy
import pcbooth.core.job
from pcbooth.modules.background import Background
from pcbooth.modules.camera import Camera
from pcbooth.modules.renderer import RendererWrapper
import pcbooth.modules.job_utilities as ju
import logging
import re
from typing import List, Generator, Any
from mathutils import Vector
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class Stackup(pcbooth.core.job.Job):
    """
    PCB stackup image rendering job.

    This module handles rendering static images of a PCB in exploded view.
    Each layer gets rendered by hiding all the layers above it.

    Yields renders named layer<idx>, starting from 1, e.g. layer1.png, layer2.png...

    Warning: this job is only compatible with models recognized as PCB (Studio.is_pcb == True) generated using gerber2blend (and optionally picknblend).
    The model has to be generated with STACKUP: True setting and contain separate layer objects containing "PCB_layer" in name.
    """

    def _override_studio(self) -> None:
        if background := Background.get("transparent"):
            self.studio.backgrounds = [background]
        if camera := Camera.get("FRONT"):
            self.studio.cameras = [camera]
        self.studio.positions = ["TOP"]

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        if not self.studio.is_pcb:
            logger.warning("This is not a supported PCB model type, skipping this job.")
            return
        rendered_children = self.studio.rendered_obj.children
        layers = sorted(
            [layer for layer in rendered_children if "PCB_layer" in layer.name],
            key=get_idx,
        )
        if len(layers) < 2:
            logger.warning("No layers found in this PCB model, skipping this job.")
            return

        renderer = RendererWrapper()
        self.update_status(len(layers))

        position = self.studio.positions[0]
        background = self.studio.backgrounds[0]
        camera = self.studio.cameras[0]
        components = self.studio.bottom_components + self.studio.top_components
        if solder := bpy.data.objects.get("Solder", None):  # hide PCB model solder object if present
            components.append(solder)
        self.studio.change_position(position)
        Background.use(background)
        camera.change_position(position)

        with (
            ju.position_override(layers, move_layers, self.studio.rendered_obj),
            ju.shadow_override(layers),
            camera.dof_override(),
            solder_switch_override(),
        ):
            with ju.hide_override(components, hide_viewport=True):
                camera.frame_selected(self.studio.rendered_obj)

            with ju.hide_override(components + layers):
                for idx, layer in enumerate(layers):
                    layer.hide_render = False
                    filename = f"layer{abs(idx-len(layers))}"
                    renderer.render(camera.object, filename)
                    renderer.thumbnail(camera.object, filename)
                    renderer.clear_cache()
                    self.update_status()


def get_idx(object: bpy.types.Object) -> int:
    """Get index from the object name"""
    match = re.search(r"(\d+)$", object.name)
    return int(match.group(1)) if match else 0


def move_layers(layers: List[bpy.types.Object]) -> None:
    """
    Spread PCB layers vertically and add slight offset in Y axis based on board dimensions.
    """
    y_offset = layers[0].dimensions.y / 20
    z_offset = layers[0].dimensions.x / 7.5
    offset = Vector((0, y_offset, z_offset))  # type: ignore
    for i, layer in enumerate(layers):
        if i == (len(layers) - 1):
            i -= 1
        if i == 0:
            continue
        layer.delta_location = i * offset


@contextmanager
def solder_switch_override() -> Generator[None, Any, None]:
    """Context manager for temporarily overriding the Solder Switch node in the PCB's main material during stackup rendering."""
    try:
        solder_switch_node = bpy.data.node_groups["Color_group"].nodes["Solder_Switch"]
        solder_switch_node.inputs[0].default_value = 1.0  # type: ignore
        yield
    except (AttributeError, RuntimeError, KeyError):
        pass
    finally:
        solder_switch_node.inputs[0].default_value = 0.0  # type: ignore
