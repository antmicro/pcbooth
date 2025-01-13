import bpy
import pcbooth.core.job
from pcbooth.modules.background import Background
from pcbooth.modules.camera import Camera
from pcbooth.modules.renderer import FFmpegWrapper, RendererWrapper
import logging

logger = logging.getLogger(__name__)


class FlipTransition(pcbooth.core.job.Job):
    """
    Camera transitions animation rendering job.

    This module handles rendering animations showcasing the model (usually PCB)
    flipped from TOP to BOTTOM position. Flips will be rendered for all cameras
    specified in config file.
    Always overrides background to "transparent" and positions to "TOP" and "BOTTOM".

    Yields renders named <camera_angle><position initial>_<camera_angle><position initial>
    e.g. rightT_leftT.webp, for each combination.
    """

    def _override_studio(self) -> None:
        if background := Background.get("transparent"):
            self.studio.backgrounds = [background]
        self.studio.positions = ["TOP", "BOTTOM"]

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        ffmpeg = FFmpegWrapper()
        renderer = RendererWrapper()
        Background.use(self.studio.backgrounds[0])
        total_renders = len(self.studio.cameras)
        self.update_status(total_renders)
        self.create_model_keyframes()
        for camera in self.studio.cameras:
            filename = f"{camera.name.lower()}T_{camera.name.lower()}B"
            rev_filename = f"{camera.name.lower()}B_{camera.name.lower()}T"
            self.create_camera_keyframes(camera)
            renderer.render_animation(camera.object, filename)
            ffmpeg.run(filename, filename)
            ffmpeg.reverse(filename, rev_filename)
            self.update_status()
        ffmpeg.clear_frames()

    def create_model_keyframes(self) -> None:
        scene = bpy.context.scene

        # create rendered object keyframes
        self.studio.change_position("TOP")
        self.studio.rendered_obj.keyframe_insert(
            data_path="rotation_euler", frame=scene.frame_start
        )

        self.studio.change_position("BOTTOM")
        self.studio.rendered_obj.keyframe_insert(
            data_path="rotation_euler", frame=scene.frame_end
        )

    def create_camera_keyframes(self, camera: Camera) -> None:
        scene = bpy.context.scene

        # create start camera + focus keyframes
        camera.change_position("TOP")
        camera.add_keyframe(scene.frame_start)

        camera.add_intermediate_keyframe(
            self.studio.rendered_obj, progress=0.3, zoom=1.4
        )
        # camera.add_intermediate_keyframe(self.studio.rendered_obj, progress=0.5, zoom=1.4)
        camera.add_intermediate_keyframe(
            self.studio.rendered_obj, progress=0.7, zoom=1.4
        )

        # create end camera + focus keyframes
        camera.change_position("BOTTOM")
        camera.add_keyframe(scene.frame_end)
