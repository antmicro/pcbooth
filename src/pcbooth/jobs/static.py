import bpy
import pcbooth.core.job
from pcbooth.modules.background import Background
from pcbooth.modules.renderer import RendererWrapper
from pcbooth.modules.custom_utilities import get_top_parent
import logging

logger = logging.getLogger(__name__)


class Static(pcbooth.core.job.Job):
    """
    Static image rendering job.

    This module handles rendering static images of a model (usually PCBs)
    using various camera angles and on selected backgrounds.

    Yields renders named <camera_angle><position initial>_<background name>
    e.g. rightT_paper_black.png, for each combination.
    """

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        renderer = RendererWrapper()
        total_renders = (
            len(self.studio.positions)
            * len(self.studio.cameras)
            * len(self.studio.backgrounds)
        )
        self.update_status(total_renders)

        for position in self.studio.positions:
            self.studio.change_position(position)
            Background.update_position(self.studio.top_parent)
            for background in self.studio.backgrounds:
                Background.use(background)
                for camera in self.studio.cameras:
                    camera.change_position(position)
                    filename = f"{camera.name.lower()}{position[0]}_{background.name}"
                    renderer.render(camera.object, filename)
                    renderer.thumbnail(camera.object, filename)
                    renderer.clear_cache()
                    self.update_status()
