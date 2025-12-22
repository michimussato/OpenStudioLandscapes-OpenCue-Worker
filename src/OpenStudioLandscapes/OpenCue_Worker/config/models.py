import enum
import pathlib

from dagster import get_dagster_logger
from pydantic import (
    Field,
    PositiveInt,
)

LOGGER = get_dagster_logger(__name__)

from OpenStudioLandscapes.engine.config.models import FeatureBaseModel

from OpenStudioLandscapes.OpenCue_Worker import dist

config_default = pathlib.Path(__file__).parent.joinpath("config_default.yml")
CONFIG_STR = config_default.read_text()


class Branches(enum.StrEnum):
    main = "main"


class Config(FeatureBaseModel):

    feature_name: str = dist.name

    definitions: str = "OpenStudioLandscapes.OpenCue_Worker.definitions"

    compose_scope: str = "worker"

    flamenco_worker_NUM_SERVICES: int = Field(
        default=5,
        description="Number of workers to simulate in parallel.",
    )

    flamenco_worker_PADDING: int = Field(
        default=3,
    )

    # EXPANDABLE PATHS
    # @property
    # def MOUNTED_VOLUME_expanded(self) -> pathlib.Path:
    #     LOGGER.debug(f"{self.env = }")
    #     if self.env is None:
    #         raise KeyError("`env` is `None`.")
    #     LOGGER.debug(f"Expanding {self.MOUNTED_VOLUME}...")
    #     ret = pathlib.Path(
    #         self.MOUNTED_VOLUME.expanduser()
    #         .as_posix()
    #         .format(
    #             **{
    #                 "FEATURE": self.feature_name,
    #                 **self.env,
    #             }
    #         )
    #     )
    #     return ret
