import bpy
import pcbooth.core.job
from pcbooth.modules.background import Background
from pcbooth.modules.camera import Camera
from pcbooth.modules.renderer import FFmpegWrapper, RendererWrapper
from pcbooth.modules.custom_utilities import clear_animation_data
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
                self.update_status()
                clear_animation_data()
        ffmpeg.clear_frames()

    def create_keyframes(
        self, camera_start: Camera, camera_end: Camera, position: str
    ) -> None:
        scene = bpy.context.scene

        # create start camera + focus keyframes
        camera_start.add_keyframe(scene.frame_start)

        # override camera_start with camera_end's data
        camera_start.object.matrix_world = camera_end.object.matrix_world.copy()
        camera_start.object.data.dof.focus_distance = camera_end.focuses[position][0]  # type: ignore
        camera_start.object.data.dof.aperture_fstop = camera_end.focuses[position][1]  # type: ignore

        # create end camera + focus keyframes
        camera_start.add_keyframe(scene.frame_end)

        camera_start.add_intermediate_keyframe(
            self.studio.rendered_obj, progress=0.2, zoom=1.1
        )
        camera_start.add_intermediate_keyframe(
            self.studio.top_parent, progress=0.5, zoom=1.1
        )
        camera_start.add_intermediate_keyframe(
            self.studio.rendered_obj, progress=0.8, zoom=1.1
        )
