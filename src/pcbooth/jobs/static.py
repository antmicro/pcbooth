from pcbooth.core.job import UserAnimationJob
from pcbooth.modules.background import Background
from pcbooth.modules.renderer import RendererWrapper
import logging
import bpy

logger = logging.getLogger(__name__)


class Static(UserAnimationJob):
    """
    Static image rendering job.

    This module handles rendering static images of a model (usually PCBs)
    using various camera angles and on selected backgrounds.
    Rendering selected frames from user-predefined animation data is supported.

    Yields renders named <camera_angle><position initial>_<background name>
    e.g. rightT_paper_black.png, for each combination.
    """

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """

        renderer = RendererWrapper()
        total_renders = (
            len(self.studio.positions) * len(self.studio.cameras) * len(self.studio.backgrounds) * len(self.frames)
        )
        self.update_status(total_renders)
        for position in self.studio.positions:
            self.studio.change_position(position)
            Background.update_position(self.studio.top_parent)
            for background in self.studio.backgrounds:
                Background.use(background)
                for camera in self.studio.cameras:
                    camera.change_position(position)

                    if self.has_animation_data:
                        self.studio.add_studio_keyframes(camera)

                    for frame in self.frames:
                        bpy.context.scene.frame_set(frame)
                        filename = f"{camera.name.lower()}{position[0]}_{background.name}{self.get_frame_suffix(frame)}"

                        renderer.render(camera.object, filename)
                        renderer.thumbnail(camera.object, filename)
                        renderer.clear_cache()
                        self.update_status()
