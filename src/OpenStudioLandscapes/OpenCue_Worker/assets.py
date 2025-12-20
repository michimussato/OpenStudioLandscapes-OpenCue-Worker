import copy
import enum
import pathlib
import textwrap
import urllib.parse
from typing import Dict, Generator, List, Union

import yaml
from dagster import (
    AssetExecutionContext,
    AssetIn,
    AssetKey,
    AssetMaterialization,
    AssetsDefinition,
    MetadataValue,
    Output,
    asset,
)
from OpenStudioLandscapes.engine.common_assets.compose import get_compose
from OpenStudioLandscapes.engine.common_assets.compose_scope import (
    get_compose_scope_group__cmd,
)
from OpenStudioLandscapes.engine.common_assets.docker_compose_graph import (
    get_docker_compose_graph,
)
from OpenStudioLandscapes.engine.common_assets.feature import get_feature__CONFIG
from OpenStudioLandscapes.engine.common_assets.feature_out import get_feature_out_v2
from OpenStudioLandscapes.engine.common_assets.group_in import (
    get_feature_in,
    get_feature_in_parent,
)
from OpenStudioLandscapes.engine.common_assets.group_out import get_group_out
from OpenStudioLandscapes.engine.config.models import ConfigEngine, DockerConfigModel
from OpenStudioLandscapes.engine.constants import *
from OpenStudioLandscapes.engine.enums import *
from OpenStudioLandscapes.engine.link.models import OpenStudioLandscapesFeatureIn
from OpenStudioLandscapes.engine.policies.retry import build_docker_image_retry_policy
from OpenStudioLandscapes.engine.utils import *
from OpenStudioLandscapes.engine.utils.docker.compose_dicts import *

from OpenStudioLandscapes.OpenCue_Worker import dist
from OpenStudioLandscapes.OpenCue_Worker.config.models import CONFIG_STR, Config
from OpenStudioLandscapes.OpenCue_Worker.constants import *

# Override default ConfigParent
from OpenStudioLandscapes.OpenCue.config.models import Config as ConfigParent
from OpenStudioLandscapes.OpenCue.constants import (
    ASSET_HEADER as ASSET_HEADER_FEATURE_IN,
)

# https://github.com/yaml/pyyaml/issues/722#issuecomment-1969292770
yaml.SafeDumper.add_multi_representer(
    data_type=enum.Enum,
    representer=yaml.representer.SafeRepresenter.represent_str,
)

# https://github.com/yaml/pyyaml/issues/722#issuecomment-1969292770
yaml.SafeDumper.add_multi_representer(
    data_type=enum.Enum,
    representer=yaml.representer.SafeRepresenter.represent_str,
)


compose_scope_group__cmd: AssetsDefinition = get_compose_scope_group__cmd(
    ASSET_HEADER=ASSET_HEADER,
)

CONFIG: AssetsDefinition = get_feature__CONFIG(
    ASSET_HEADER=ASSET_HEADER,
    CONFIG_STR=CONFIG_STR,
    search_model_of_type=Config,
)

feature_in: AssetsDefinition = get_feature_in(
    ASSET_HEADER=ASSET_HEADER,
    ASSET_HEADER_BASE=ASSET_HEADER_BASE,
    ASSET_HEADER_FEATURE_IN=ASSET_HEADER_FEATURE_IN,
)

group_out: AssetsDefinition = get_group_out(
    ASSET_HEADER=ASSET_HEADER,
)


docker_compose_graph: AssetsDefinition = get_docker_compose_graph(
    ASSET_HEADER=ASSET_HEADER,
)


compose: AssetsDefinition = get_compose(
    ASSET_HEADER=ASSET_HEADER,
)


feature_out_v2: AssetsDefinition = get_feature_out_v2(
    ASSET_HEADER=ASSET_HEADER,
)


# Produces
# - feature_in_parent
# - CONFIG_PARENT
# if ConfigParent is or type FeatureBaseModel
feature_in_parent: Union[AssetsDefinition, None] = get_feature_in_parent(
    ASSET_HEADER=ASSET_HEADER,
    config_parent=ConfigParent,
)


@asset(
    **ASSET_HEADER,
    ins={
        "feature_in": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "feature_in"]),
        ),
        "CONFIG": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG"]),
        ),
    },
    retry_policy=build_docker_image_retry_policy,
)
def build_docker_image(
    context: AssetExecutionContext,
    feature_in: OpenStudioLandscapesFeatureIn,  # pylint: disable=redefined-outer-name
    CONFIG: Config,  # pylint: disable=redefined-outer-name
) -> Generator[Output[Dict] | AssetMaterialization, None, None]:
    """ """

    env: Dict = CONFIG.env

    docker_config_json: pathlib.Path = (
        feature_in.openstudiolandscapes_base.docker_config_json
    )

    config_engine: ConfigEngine = CONFIG.config_engine

    docker_config: DockerConfigModel = config_engine.openstudiolandscapes__docker_config

    docker_image: Dict = feature_in.openstudiolandscapes_base.docker_image_base

    docker_file = pathlib.Path(
        env["DOT_LANDSCAPES"],
        env.get("LANDSCAPE", "default"),
        f"{dist.name}",
        "__".join(context.asset_key.path),
        "Dockerfiles",
        "Dockerfile",
    )

    docker_file.parent.mkdir(parents=True, exist_ok=True)

    #################################################

    (
        image_name,
        image_prefixes,
        tags,
        build_base_parent_image_prefix,
        build_base_parent_image_name,
        build_base_parent_image_tags,
    ) = get_image_metadata(
        context=context,
        docker_image=docker_image,
        docker_config=docker_config,
        env=env,
    )

    #################################################

    # @formatter:off
    docker_file_str = textwrap.dedent(
        """\
        # {auto_generated}
        # {dagster_url}
        FROM {parent_image} AS {image_name}
        LABEL authors="{AUTHOR}"

        ARG DEBIAN_FRONTEND=noninteractive

        ENV CONTAINER_TIMEZONE={TIMEZONE}
        ENV SET_CONTAINER_TIMEZONE=true

        SHELL ["/bin/bash", "-c"]

        RUN apt-get update && apt-get upgrade -y

        # WORKDIR /workdir
        # USER user

        # RUN commands
        # [...]

        RUN apt-get clean

        ENTRYPOINT []
        """
    ).format(
        auto_generated=f"AUTO-GENERATED by Dagster Asset {'__'.join(context.asset_key.path)}",
        dagster_url=urllib.parse.quote(
            f"http://localhost:3000/asset-groups/{'%2F'.join(context.asset_key.path)}",
            safe=":/%",
        ),
        image_name=image_name,
        # Todo: this won't work as expected if len(tags) > 1
        parent_image=f"{build_base_parent_image_prefix}{build_base_parent_image_name}:{build_base_parent_image_tags[0]}",
        **env,
    )
    # @formatter:on

    with open(docker_file, "w") as fw:
        fw.write(docker_file_str)

    with open(docker_file, "r") as fr:
        docker_file_content = fr.read()

    #################################################

    image_data, logs = create_image(
        context=context,
        image_name=image_name,
        image_prefixes=image_prefixes,
        tags=tags,
        docker_image=docker_image,
        docker_config=docker_config,
        docker_config_json=docker_config_json,
        docker_file=docker_file,
    )

    yield Output(image_data)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(image_data),
            "docker_file": MetadataValue.md(f"```shell\n{docker_file_content}\n```"),
            "logs": MetadataValue.json(logs),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "CONFIG": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG"]),
        ),
    },
)
def compose_networks(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
) -> Generator[
    Output[Dict[str, Dict[str, Dict[str, str]]]] | AssetMaterialization, None, None
]:

    env: Dict = CONFIG.env

    compose_network_mode = DockerComposePolicies.NETWORK_MODE.BRIDGE

    docker_dict = get_network_dicts(
        context=context,
        compose_network_mode=compose_network_mode,
        env=env,
    )

    docker_yaml = yaml.dump(docker_dict)

    yield Output(docker_dict)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(docker_dict),
            "compose_network_mode": MetadataValue.text(compose_network_mode.value),
            "docker_yaml": MetadataValue.md(f"```yaml\n{docker_yaml}\n```"),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "CONFIG": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG"]),
        ),
        "build": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "build_docker_image"]),
        ),
        "compose_networks": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose_networks"]),
        ),
    },
)
def compose_override(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
    build: Dict,  # pylint: disable=redefined-outer-name
    compose_networks: Dict,  # pylint: disable=redefined-outer-name
) -> Generator[Output[Dict] | AssetMaterialization, None, None]:
    """ """

    env: Dict = CONFIG.env

    config_engine: ConfigEngine = CONFIG.config_engine

    network_dict = {}
    ports_dict = {}

    if "networks" in compose_networks:
        network_dict = {"networks": list(compose_networks.get("networks", {}).keys())}
        ports_dict = {
            "ports": [
                f"{CONFIG.ENV_VAR_PORT_HOST}:{CONFIG.ENV_VAR_PORT_CONTAINER}",
            ]
        }
    elif "network_mode" in compose_networks:
        network_dict = {"network_mode": compose_networks["network_mode"]}

    host_mount: pathlib.Path = CONFIG.MOUNTED_VOLUME_expanded
    host_mount.mkdir(parents=True, exist_ok=True)

    volumes_dict = {
        "volumes": [
            f"{host_mount.as_posix()}:/some/host/dir:rw",
        ],
    }

    # For portability, convert absolute volume paths to relative paths

    _volume_relative = []

    for v in volumes_dict["volumes"]:

        host, container = v.split(":", maxsplit=1)

        volume_dir_host_rel_path = get_relative_path_via_common_root(
            context=context,
            path_src=CONFIG.docker_compose_expanded,
            path_dst=pathlib.Path(host),
            path_common_root=pathlib.Path(env["DOT_LANDSCAPES"]),
        )

        _volume_relative.append(
            f"{volume_dir_host_rel_path.as_posix()}:{container}",
        )

    volumes_dict = {
        "volumes": [
            *_volume_relative,
        ],
    }

    command = []

    service_name = "template"
    container_name, host_name = get_docker_compose_names(
        context=context,
        service_name=service_name,
        landscape_id=env.get("LANDSCAPE", "default"),
        domain_lan=config_engine.openstudiolandscapes__domain_lan,
    )
    # container_name = "--".join([service_name, env.get("LANDSCAPE", "default")])
    # host_name = ".".join(
    #     [service_name, env["OPENSTUDIOLANDSCAPES__DOMAIN_LAN"]]
    # )

    docker_dict = {
        "services": {
            service_name: {
                "container_name": container_name,
                "hostname": host_name,
                "domainname": config_engine.openstudiolandscapes__domain_lan,
                # "mac_address": ":".join(re.findall(r"..", env["HOST_ID"])),
                "restart": DockerComposePolicies.RESTART_POLICY.ALWAYS.value,
                # "image": "${DOT_OVERRIDES_REGISTRY_NAMESPACE:-docker.io/openstudiolandscapes}/%s:%s"
                # % (build["image_name"], build["image_tags"][0]),
                "image": "%s%s:%s"
                % (
                    build["image_prefixes"],
                    build["image_name"],
                    build["image_tags"][0],
                ),
                **copy.deepcopy(volumes_dict),
                **copy.deepcopy(network_dict),
                **copy.deepcopy(ports_dict),
                # "environment": {
                # },
                # "healthcheck": {
                # },
                # "command": command,
            },
        },
    }

    docker_yaml = yaml.dump(docker_dict)

    yield Output(docker_dict)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(docker_dict),
            "docker_yaml": MetadataValue.md(f"```yaml\n{docker_yaml}\n```"),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "compose_override": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose_override"]),
        ),
    },
)
def compose_maps(
    context: AssetExecutionContext,
    **kwargs,  # pylint: disable=redefined-outer-name
) -> Generator[Output[List[Dict]] | AssetMaterialization, None, None]:

    ret = list(kwargs.values())

    context.log.info(ret)

    yield Output(ret)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(ret),
        },
    )
