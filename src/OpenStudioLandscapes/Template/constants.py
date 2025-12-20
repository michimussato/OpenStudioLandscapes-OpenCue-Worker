__all__ = [
    "DOCKER_USE_CACHE",
    "GROUP",
    "KEY",
    "ASSET_HEADER",
    "ENVIRONMENT",
    "COMPOSE_SCOPE",
]

import pathlib
from typing import Generator, MutableMapping

from dagster import (
    asset,
    Output,
    AssetMaterialization,
    MetadataValue,
    AssetExecutionContext,
)

from OpenStudioLandscapes.engine.utils import *
from OpenStudioLandscapes.engine.constants import DOCKER_USE_CACHE_GLOBAL, THIRD_PARTY
from OpenStudioLandscapes.engine.exceptions import ComposeScopeException


DOCKER_USE_CACHE = DOCKER_USE_CACHE_GLOBAL or False


GROUP = "Your_New_Feature"
KEY = [GROUP]

ASSET_HEADER = {
    "group_name": GROUP,
    "key_prefix": KEY,
    "compute_kind": "python",
}

# @formatter:off
ENVIRONMENT = {
    "DOCKER_USE_CACHE": DOCKER_USE_CACHE,
    # "CONFIGS_ROOT": pathlib.Path(
    #     get_configs_root(pathlib.Path(__file__)),
    # )
    # .expanduser()
    # .as_posix(),
    # "DATA_ROOT": pathlib.Path(
    #     get_data_root(pathlib.Path(__file__)),
    # )
    # .expanduser()
    # .as_posix(),
    # "BIN_ROOT": pathlib.Path(
    #     get_bin_root(pathlib.Path(__file__)),
    # )
    # .expanduser()
    # .as_posix(),
}
# @formatter:on

# Todo
#  - [ ] This is a bit hacky
#  - [ ] Externalize
_module = __name__
_parent = '.'.join(_module.split('.')[:-1])
_definitions = '.'.join([_parent, "definitions"])

COMPOSE_SCOPE = None
for i in THIRD_PARTY:
    if i["module"] == _definitions:
        COMPOSE_SCOPE = i["compose_scope"]
        break

if COMPOSE_SCOPE is None:
    raise ComposeScopeException(
        "No compose_scope found for module '%s'. Is the module enabled?" % _module
    )


@asset(
    **ASSET_HEADER,
    description="",
)
def constants(
    context: AssetExecutionContext,
) -> Generator[Output[MutableMapping] | AssetMaterialization, None, None]:
    """ """

    _constants = dict()

    _constants["DOCKER_USE_CACHE"] = DOCKER_USE_CACHE
    _constants["ASSET_HEADER"] = ASSET_HEADER
    _constants["ENVIRONMENT"] = ENVIRONMENT

    yield Output(_constants)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(_constants),
        },
    )
