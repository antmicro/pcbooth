import bpy
import pcbooth.core.job
from pcbooth.modules.background import Background
from pcbooth.modules.camera import Camera
from pcbooth.modules.renderer import FFmpegWrapper, RendererWrapper
import logging
from itertools import combinations

logger = logging.getLogger(__name__)


class CameraTransition(pcbooth.core.job.Job):
    """
    Camera transitions animation rendering job.

    This module handles rendering animations showcasing the model (usually PCB)
    transitioning from one camera angle to another. Transitions will be generated for all camera combinations specified in the configuration,
    but only within the same position (for example left to right bottom side, but never left top to right bottom)
    Always overrides background to "transparent".

    Yields renders named <camera_angle><position initial>_<camera_angle><position initial>
    e.g. rightT_leftT.webp, for each combination.
    """

    def _override_studio(self) -> None:
        if background := Background.get("transparent"):
            self.studio.backgrounds = [background]
        if self.studio.is_ortho:
            """
            Disables Camera transition rendering job when ORTHO_CAM is enabled in config.
            This is because in current implementation causes excessive camera movement when interpolated due to large focal length.
            To be fixed in future, possibly by making ORTHO_CAM to enable spawning ortho type cameras instead of perspective ones.
            """
            logger.warning(
                "This job is unavailable for use with ortho-like camera (SCENE/ORTHO_CAM setting is enabled)."
            )
            self.studio.cameras = []

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        ffmpeg = FFmpegWrapper()
        renderer = RendererWrapper()
        Background.use(self.studio.backgrounds[0])
        pairs = list(combinations(self.studio.cameras, 2))
        total_renders = len(pairs) * len(self.studio.positions)
        logger.debug(f"Combined pairs: {pairs}")
        self.update_status(total_renders)
        for position in self.studio.positions:
            self.studio.change_position(position)
            for pair in pairs:
                camera_start = pair[0]
                camera_end = pair[1]
                camera_start.change_position(position)
                camera_end.change_position(position)

                filename = f"{camera_start.name.lower()}{position[0]}_{camera_end.name.lower()}{position[0]}"
                rev_filename = f"{camera_end.name.lower()}{position[0]}_{camera_start.name.lower()}{position[0]}"
                self.create_keyframes(camera_start, camera_end, position)
                renderer.render_animation(camera_start.object, filename)
                ffmpeg.run(filename, filename)
                ffmpeg.reverse(filename, rev_filename)
                ffmpeg.thumbnail(filename)
                ffmpeg.thumbnail(rev_filename)
                self.update_status()
                self.studio.clear_animation_data()
        ffmpeg.clear_frames()

    def create_keyframes(self, camera_start: Camera, camera_end: Camera, position: str) -> None:
        scene = bpy.context.scene

        # create start camera + focus keyframes
        camera_start.add_keyframe(scene.frame_start)

        # override camera_start with camera_end's data
        camera_start.object.matrix_world = camera_end.object.matrix_world.copy()
        camera_start.object.data.dof.focus_distance = camera_end.focuses[position][0]  # type: ignore
        camera_start.object.data.dof.aperture_fstop = camera_end.focuses[position][1]  # type: ignore

        # create end camera + focus keyframes
        camera_start.add_keyframe(scene.frame_end)

        # exception for when left to right camera transition is requested
        if all(cam in ["LEFT", "RIGHT"] for cam in [camera_start.name, camera_end.name]):
            if camera_mid := Camera.get("FRONT"):
                camera_start.object.matrix_world = camera_mid.object.matrix_world.copy()

        # create intermediate frame with camera zoom out
        camera_start.add_intermediate_keyframe(self.studio.rendered_obj, progress=0.5, zoom_out=1.2)
