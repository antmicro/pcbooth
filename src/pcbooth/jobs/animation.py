from pcbooth.core.job import Job
from pcbooth.modules.background import Background
from pcbooth.modules.renderer import FFmpegWrapper, RendererWrapper
import logging
from pcbooth.modules.camera import Camera
import pcbooth.modules.job_utilities as ju

logger = logging.getLogger(__name__)


class Animation(Job):
    """Animation rendering job.

    This module handles rendering animation from keyframes that are predefined by user and saved within rendered .blend file.
    It supports using various camera angles and selected backgrounds.

    Yields renders named <camera_angle><position initial>_<background name>_animation
    e.g. rightT_paper_black_animation.webm, for each combination.
    '_reversed' suffix is added for reversed animations.
    """

    def iterate(self) -> None:
        """Main loop of the module to be run within execute() method."""
        if not any(self.studio.animation_data.values()):
            logger.warning("There's no user-defined actions in this .blend file, nothing to render within this job.")
            return

        with ju.user_animation_override(self.studio):
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
                        self.add_studio_keyframes(camera)

                        filename = f"{camera.name.lower()}{position[0]}_{background.name}_animation"
                        rev_filename = f"{camera.name.lower()}{position[0]}_{background.name}_animation_reversed"
                        renderer.render_animation(camera.object, filename)

                        ffmpeg.run(filename, filename)
                        ffmpeg.reverse(filename, rev_filename)
                        ffmpeg.thumbnail(filename)
                        ffmpeg.thumbnail(rev_filename)
                        self.update_status()

            ffmpeg.clear_frames()

    def add_studio_keyframes(self, camera: Camera) -> None:
        for frame in range(self.studio.frame_start, self.studio.frame_end):
            camera.add_intermediate_keyframe(
                rendered_obj=self.studio.top_parent, frame=frame, frame_selected=True, focus=True
            )
