import enum
import pathlib

from dagster import get_dagster_logger
from pydantic import (
    Field,
    PositiveInt,
)

LOGGER = get_dagster_logger(__name__)

from OpenStudioLandscapes.engine.config.str_gen import get_config_str
from OpenStudioLandscapes.engine.config.models import FeatureBaseModel

from OpenStudioLandscapes.OpenCue_Worker import dist

config_default = pathlib.Path(__file__).parent.joinpath("config_default.yml")


class Branches(enum.StrEnum):
    main = "main"


class Config(FeatureBaseModel):

    feature_name: str = dist.name

    compose_scope: str = "worker"

    opencue_rqd_worker: str = "opencue-rqd-worker"

    opencue_worker_NUM_SERVICES: PositiveInt = Field(
        default=1,
        description="Number of workers to simulate in parallel.",
    )

    opencue_worker_PADDING: PositiveInt = Field(
        default=3,
    )

    opencue_worker_storage: pathlib.Path = Field(
        default=pathlib.Path("{DOT_LANDSCAPES}/{LANDSCAPE}/{FEATURE}/storage"),
    )

    # EXPANDABLE PATHS
    @property
    def opencue_worker_storage_expanded(self) -> pathlib.Path:
        LOGGER.debug(f"{self.env = }")
        if self.env is None:
            raise KeyError("`env` is `None`.")
        LOGGER.debug(f"Expanding {self.opencue_worker_storage}...")
        ret = pathlib.Path(
            self.opencue_worker_storage.expanduser()
            .as_posix()
            .format(
                **{
                    "FEATURE": self.feature_name,
                    **self.env,
                }
            )
        )
        return ret


CONFIG_STR = get_config_str(
    Config=Config,
)

