import bpy
import pcbooth.core.job
from pcbooth.modules.background import Background
from pcbooth.modules.camera import Camera
from pcbooth.modules.renderer import FFmpegWrapper, RendererWrapper
import logging
from itertools import combinations
from typing import Tuple

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

    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        """
        ffmpeg = FFmpegWrapper()
        renderer = RendererWrapper()
        Background.use(self.studio.backgrounds[0])
        pairs = list(combinations(self.studio.positions, 2))
        total_renders = len(pairs) * len(self.studio.cameras)
        self.update_status(total_renders)

        for pair in pairs:
            self.create_model_keyframes(pair)
            for camera in self.studio.cameras:
                pos_start = pair[0]
                pos_end = pair[1]

                filename = f"{camera.name.lower()}{pos_start[0]}_{camera.name.lower()}{pos_end[0]}"
                rev_filename = f"{camera.name.lower()}{pos_end[0]}_{camera.name.lower()}{pos_start[0]}"
                self.create_camera_keyframes(camera, pair)
                renderer.render_animation(camera.object, filename)
                ffmpeg.run(filename, filename)
                ffmpeg.reverse(filename, rev_filename)
                ffmpeg.thumbnail(filename)
                ffmpeg.thumbnail(rev_filename)
                self.update_status()
            self.studio.clear_animation_data()
        ffmpeg.clear_frames()

    def create_model_keyframes(self, pair: Tuple[str, str]) -> None:
        scene = bpy.context.scene

        # create rendered object keyframes
        self.studio.change_position(pair[0])
        self.studio.top_parent.keyframe_insert(data_path="rotation_euler", frame=scene.frame_start)

        self.studio.change_position(pair[1])
        self.studio.top_parent.keyframe_insert(data_path="rotation_euler", frame=scene.frame_end)

    def create_camera_keyframes(self, camera: Camera, pair: Tuple[str, str]) -> None:
        scene = bpy.context.scene

        # create start camera keyframes
        camera.change_position(pair[0])
        camera.add_keyframe(scene.frame_start)

        # create end camera keyframes
        camera.change_position(pair[1])
        camera.add_keyframe(scene.frame_end)

        # create intermediate frame with camera zoom out
        camera.add_intermediate_keyframe(self.studio.top_parent, progress=0.5, zoom_out=1.35, frame_selected=False)
