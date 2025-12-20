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

    compose_scope: str = "worker"

    definitions: str = "OpenStudioLandscapes.OpenCue_Worker.definitions"

    ENV_VAR_PORT_HOST: PositiveInt = Field(
        default=1234,
        description="The host port.",
        frozen=True,
    )
    ENV_VAR_PORT_CONTAINER: PositiveInt = Field(
        default=2345,
        description="The Ayon container port.",
        frozen=False,
    )

    MOUNTED_VOLUME: pathlib.Path = Field(
        description="The host side mounted volume.",
        default=pathlib.Path("{DOT_LANDSCAPES}/{LANDSCAPE}/{FEATURE}/volume"),
    )

    # EXPANDABLE PATHS
    @property
    def MOUNTED_VOLUME_expanded(self) -> pathlib.Path:
        LOGGER.debug(f"{self.env = }")
        if self.env is None:
            raise KeyError("`env` is `None`.")
        LOGGER.debug(f"Expanding {self.MOUNTED_VOLUME}...")
        ret = pathlib.Path(
            self.MOUNTED_VOLUME.expanduser()
            .as_posix()
            .format(
                **{
                    "FEATURE": self.feature_name,
                    **self.env,
                }
            )
        )
        return ret
