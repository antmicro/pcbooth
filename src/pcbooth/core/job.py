"""Class representing a single module of the pipeline."""

import logging
from abc import ABC, abstractmethod
from pcbooth.modules.studio import Studio
from pcbooth.modules.job_utilities import user_animation_override
from pcbooth.modules.custom_utilities import set_frame_range
from copy import copy
from typing import List, Optional, Dict, Any, Set, Literal, List
from pydantic import BaseModel
from contextlib import nullcontext

logger = logging.getLogger(__name__)


class Job(ABC):
    """Represents a single module of the pipeline, for example: transition."""

    class ParameterSchema(BaseModel):
        """
        Optional job parameters pydantic schema class.
        Overwrite this in deriving classes to add their own parameters.
        """

        pass

    def __init__(self, params: Dict[str, Any]) -> None:
        self._iter: int = 0
        self._total: int = 1
        self.studio: Studio
        self.params = self._get_params(params)

    def execute(self, studio: Studio) -> None:
        """Execute the current module.

        Errors during execution can be returned by raising an exception.
        """
        self._setup(studio)
        if not self.report():
            self.iterate()
        studio.clear_animation_data()

    def _setup(self, studio: Studio) -> None:
        """
        Load and print job parameters read from Studio instance.
        """
        self._iter = 0
        self.studio = copy(studio)
        self.studio.set_frames(default=True)
        self._override_studio()
        if self.studio.__dict__ != studio.__dict__:
            logger.warning(
                f"Studio components from config will be overriden with values defined in {type(self).__name__.upper()}!"
            )

    def _override_studio(self) -> None:
        """
        Override config studio backgrounds, cameras and positions lists for the single job.
        Leave empty if no override is needed.
        Otherwise, specify them like so:
        self.studio.backgrounds = [Background.get("transparent")]
        """
        pass

    def _get_params(self, arg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get optional parameters passed with rendering job list config file and validate them using Schema class.
        Missing parameters are filled with default values.
        """
        try:
            params = dict(self.ParameterSchema(**arg))
        except TypeError:
            params = dict(self.ParameterSchema())
        logger.debug(f"Parsed rendering job parameters: {params}")
        return params

    @abstractmethod
    def iterate(self) -> None:
        """
        Main loop of the module to be run within execute() method.
        Typically render() function looped over cameras, backgrounds and positions
        specified in config file.
        """
        pass

    def update_status(self, total: Optional[int] = None) -> None:
        """
        When calling this method without argument, increment the progress counter and print progress update.
        When passing with integer argument, this method will update _total attribute used to count progress percent.
        """
        if total:
            self._total = total
            logger.info(f"Total renders: {self._total}")
            return
        self._iter += 1
        percent = self._iter / self._total * 100
        logger.info(f"### Progress: {self._iter}/{self._total} ({int(percent)}%)")

    def report(self) -> int:
        """Print job name and enabled Studio items to be used in the job."""
        logger.info(f"### {type(self).__name__.upper()} rendering job")

        items: Dict[str, Any] = {
            "rendered object positions": ", ".join(self.studio.positions),
            "cameras": (", ".join([camera.name for camera in self.studio.cameras])),
            "backgrounds": (", ".join([bg.name for bg in self.studio.backgrounds])),
        }
        if self.params:
            items["parameters"] = ", ".join(f"{key}={value}" for key, value in self.params.items())

        for item, value in items.items():
            if value:
                logger.info(f"\t* enabled {item}: {value}")
            else:
                logger.warning(f"\t* no enabled {item}!")

        if not all(items.values()):
            logger.warning("Nothing to render within this job.")
            return 1

        return 0


_DEFAULT_FRAMES = ["start", "end"]


class UserAnimationJob(Job):
    """
    Represents a single module of the pipeline with user-defined keyframes support.
    Runs within user_animation_override context.
    """

    class ParameterSchema(BaseModel):
        """
        Pydantic schema class for optional job parameters.
        Overwrite this in deriving classes to add their own parameters.
        """

        FRAMES: List[Literal["start", "end"] | int] = []

    def execute(self, studio: Studio) -> None:
        """
        Execute the current module.
        Errors during execution can be returned by raising an exception.
        """
        self._setup(studio)
        with self.context:
            self._parse_frames()
            set_frame_range(min(self.frames), max(self.frames))
            if not self.report():
                self.iterate()
        studio.clear_animation_data()

    def _setup(self, studio: Studio) -> None:
        """Load and print job parameters read from Studio instance."""
        super()._setup(studio)
        self.context = (
            user_animation_override(self.studio) if self.params.get("FRAMES", _DEFAULT_FRAMES) else nullcontext()
        )

    def get_frame_suffix(self, frame: int) -> str:
        """Get frame suffix string, can be used to add to filenames of renders."""
        frames = self.params.get("FRAMES", _DEFAULT_FRAMES)
        if not frames:
            return ""
        end_frame = max(self.frames)
        start_frame = min(self.frames)
        if frame == end_frame and "end" in frames:
            return "_end"
        elif frame == start_frame and "start" in frames:
            return "_start"
        return f"_{frame:04d}"

    def _parse_frames(self) -> None:
        """Parse FRAMES optional parameter into set of integers, changes 'start' and 'end' into corresponding first and last found keyframe."""

        frames = self.params.get("FRAMES", _DEFAULT_FRAMES)
        self.has_animation_data = True
        if not frames:
            self.has_animation_data = False
            frames = ["start"]
        frame_map = {"start": self.studio.frame_start, "end": self.studio.frame_end}
        self.frames = {frame_map.get(frame, frame) for frame in frames}
