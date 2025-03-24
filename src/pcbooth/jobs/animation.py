from pcbooth.core.job import UserAnimationJob
from pcbooth.modules.background import Background
from pcbooth.modules.renderer import FFmpegWrapper, RendererWrapper
from pydantic import BaseModel
import logging
from typing import List, Literal

logger = logging.getLogger(__name__)


class Animation(UserAnimationJob):
    """Animation rendering job.

    This module handles rendering animation from keyframes that are predefined by user and saved within rendered .blend file.
    It supports using various camera angles and selected backgrounds.

    Yields renders named <camera_angle><position initial>_<background name>_animation
    e.g. rightT_paper_black_animation.webm, for each combination.
    '_reversed' suffix is added for reversed animations.
    """

    class ParameterSchema(BaseModel):
        pass

    def iterate(self) -> None:
        """Main loop of the module to be run within execute() method."""
        if not any(self.studio.animation_data.values()):
            logger.warning("There's no user-defined actions in this .blend file, nothing to render within this job.")
            return

        ffmpeg = FFmpegWrapper()
        renderer = RendererWrapper()
        total_renders = len(self.studio.cameras) * len(self.studio.positions) * len(self.studio.backgrounds)

        self.update_status(total_renders)
        for position in self.studio.positions:
            self.studio.change_position(position)
            Background.update_position(self.studio.top_parent)
            for background in self.studio.backgrounds:
                Background.use(background)
                for camera in self.studio.cameras:
                    camera.change_position(position)
                    self.studio.add_studio_keyframes(camera)

                    filename = f"{camera.name.lower()}{position[0]}_{background.name}_animation"
                    rev_filename = f"{camera.name.lower()}{position[0]}_{background.name}_animation_reversed"
                    renderer.render_animation(camera.object, filename)

                    ffmpeg.run(filename, filename)
                    ffmpeg.reverse(filename, rev_filename)
                    ffmpeg.thumbnail(filename)
                    ffmpeg.thumbnail(rev_filename)
                    self.update_status()

        ffmpeg.clear_frames()
