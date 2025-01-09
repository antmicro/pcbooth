"""Class representing a single module of the pipeline."""

import logging
import bpy
from abc import ABC, abstractmethod
from pcbooth.modules.studio import Studio
from pcbooth.modules.custom_utilities import clear_animation_data
from copy import copy
from typing import List, Optional

logger = logging.getLogger(__name__)


class Job(ABC):
    """Represents a single module of the pipeline, for example: transition."""

    def __init__(self) -> None:
        self._iter: int = 0
        self._total: int = 1
        self.studio: Studio = None
        self._actions_backup: List[bpy.types.Action] = []

    def execute(self, studio: Studio) -> None:
        """Execute the current module.

        Errors during execution can be returned by raising an exception.
        """
        self._setup(studio)
        if not self.report():
            self.iterate()
        clear_animation_data()

    def _setup(self, studio: Studio) -> None:
        """
        Load and print job parameters read from Studio instance.
        """
        self._iter = 0
        self.studio = copy(studio)
        self._override_studio()

    def _override_studio(self):
        """
        Override config studio backgrounds, cameras and positions lists for the single job.
        Leave empty if no override is needed.
        Otherwise, specify them like so:
        self.studio.backgrounds = [Background.get("transparent")]
        """
        pass

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

        items = {
            "rendered object positions": self.studio.positions,
            "cameras": ([camera.name for camera in self.studio.cameras]),
            "backgrounds": ([bg.name for bg in self.studio.backgrounds]),
        }

        for item, value in items.items():
            if value:
                logger.info(f"\t* enabled {item}: {value}")
            else:
                logger.warning(f"\t* no enabled {item}!")

        if not all(items.values()):
            logger.warning("Nothing to render within this job.")
            return 1

        return 0
