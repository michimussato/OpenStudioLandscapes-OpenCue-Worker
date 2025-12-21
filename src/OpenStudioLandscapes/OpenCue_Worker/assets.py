import copy
import enum
import pathlib
import textwrap
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
from docker_compose_graph.yaml_tags.overrides import *
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


# @asset(
#     **ASSET_HEADER,
#     ins={
#         "feature_in": AssetIn(
#             AssetKey([*ASSET_HEADER["key_prefix"], "feature_in"]),
#         ),
#         "CONFIG": AssetIn(
#             AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG"]),
#         ),
#     },
#     retry_policy=build_docker_image_retry_policy,
# )
# def build_docker_image(
#     context: AssetExecutionContext,
#     feature_in: OpenStudioLandscapesFeatureIn,  # pylint: disable=redefined-outer-name
#     CONFIG: Config,  # pylint: disable=redefined-outer-name
# ) -> Generator[Output[Dict] | AssetMaterialization, None, None]:
#     """ """
#
#     env: Dict = CONFIG.env
#
#     docker_config_json: pathlib.Path = (
#         feature_in.openstudiolandscapes_base.docker_config_json
#     )
#
#     config_engine: ConfigEngine = CONFIG.config_engine
#
#     docker_config: DockerConfigModel = config_engine.openstudiolandscapes__docker_config
#
#     docker_image: Dict = feature_in.openstudiolandscapes_base.docker_image_base
#
#     docker_file = pathlib.Path(
#         env["DOT_LANDSCAPES"],
#         env.get("LANDSCAPE", "default"),
#         f"{dist.name}",
#         "__".join(context.asset_key.path),
#         "Dockerfiles",
#         "Dockerfile",
#     )
#
#     docker_file.parent.mkdir(parents=True, exist_ok=True)
#
#     #################################################
#
#     (
#         image_name,
#         image_prefixes,
#         tags,
#         build_base_parent_image_prefix,
#         build_base_parent_image_name,
#         build_base_parent_image_tags,
#     ) = get_image_metadata(
#         context=context,
#         docker_image=docker_image,
#         docker_config=docker_config,
#         env=env,
#     )
#
#     #################################################
#
#     # @formatter:off
#     docker_file_str = textwrap.dedent(
#         """\
#         # {auto_generated}
#         # {dagster_url}
#         FROM {parent_image} AS {image_name}
#         LABEL authors="{AUTHOR}"
#
#         ARG DEBIAN_FRONTEND=noninteractive
#
#         ENV CONTAINER_TIMEZONE={TIMEZONE}
#         ENV SET_CONTAINER_TIMEZONE=true
#
#         SHELL ["/bin/bash", "-c"]
#
#         RUN apt-get update && apt-get upgrade -y
#
#         # WORKDIR /workdir
#         # USER user
#
#         # RUN commands
#         # [...]
#
#         RUN apt-get clean
#
#         ENTRYPOINT []
#         """
#     ).format(
#         auto_generated=f"AUTO-GENERATED by Dagster Asset {'__'.join(context.asset_key.path)}",
#         dagster_url=urllib.parse.quote(
#             f"http://localhost:3000/asset-groups/{'%2F'.join(context.asset_key.path)}",
#             safe=":/%",
#         ),
#         image_name=image_name,
#         # Todo: this won't work as expected if len(tags) > 1
#         parent_image=f"{build_base_parent_image_prefix}{build_base_parent_image_name}:{build_base_parent_image_tags[0]}",
#         **env,
#     )
#     # @formatter:on
#
#     with open(docker_file, "w") as fw:
#         fw.write(docker_file_str)
#
#     with open(docker_file, "r") as fr:
#         docker_file_content = fr.read()
#
#     #################################################
#
#     image_data, logs = create_image(
#         context=context,
#         image_name=image_name,
#         image_prefixes=image_prefixes,
#         tags=tags,
#         docker_image=docker_image,
#         docker_config=docker_config,
#         docker_config_json=docker_config_json,
#         docker_file=docker_file,
#     )
#
#     yield Output(image_data)
#
#     yield AssetMaterialization(
#         asset_key=context.asset_key,
#         metadata={
#             "__".join(context.asset_key.path): MetadataValue.json(image_data),
#             "docker_file": MetadataValue.md(f"```shell\n{docker_file_content}\n```"),
#             "logs": MetadataValue.json(logs),
#         },
#     )


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


@asset(
    **ASSET_HEADER,
    ins={
        "CONFIG": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG"]),
        ),
    },
)
def prepare_volumes(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
) -> Generator[Output[Dict] | AssetMaterialization, None, None]:
    """https://www.opencue.io/docs/quick-starts/quick-start-linux/#deploying-the-opencue-sandbox-environment"""

    env: dict = CONFIG.env

    local_volumes_root = pathlib.Path(
        env["DOT_LANDSCAPES"],
        env.get("LANDSCAPE", "default"),
        f"{dist.name}",
        "__".join(context.asset_key.path),
    )

    volume_logs = local_volumes_root / "logs"
    volume_logs.mkdir(parents=True, exist_ok=True)
    volume_shots = local_volumes_root / "shots"
    volume_shots.mkdir(parents=True, exist_ok=True)

    ret = {
        "logs": volume_logs.as_posix(),
        "shots": volume_shots.as_posix(),
    }

    yield Output(ret)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(ret),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "CONFIG": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG"]),
        ),
        "CONFIG_PARENT": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG_PARENT"]),
        ),
        "compose_networks": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose_networks"]),
        ),
        "clone_repository": AssetIn(
            AssetKey([*ASSET_HEADER_FEATURE_IN["key_prefix"], "clone_repository"]),
        ),
        "prepare_volumes": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "prepare_volumes"]),
        ),
    },
    description=textwrap.dedent(
        """
        OpenCue components that are shipped 
        within a ready made 
        [`docker-compose.yml`](https://github.com/AcademySoftwareFoundation/OpenCue/blob/master/docker-compose.yml)
        only need overrides on top it.
        - Cuebot
        - RQD
        - Database
        """
    )
)
def compose_override(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
    CONFIG_PARENT: ConfigParent,  # pylint: disable=redefined-outer-name
    compose_networks: Dict,  # pylint: disable=redefined-outer-name
    clone_repository: pathlib.Path,  # pylint: disable=redefined-outer-name
    prepare_volumes: Dict,  # pylint: disable=redefined-outer-name
) -> Generator[
    Output[Dict[str, List[Dict[str, List[str]]]]] | AssetMaterialization, None, None
]:

    env: Dict = CONFIG.env

    config_engine: ConfigEngine = CONFIG.config_engine

    network_dict = {}
    # ports_dict = {}
    ports_dict_rqd = {}
    ports_dict_cuebot = {}
    ports_dict_db = {}

    if "networks" in compose_networks:
        network_dict = {"networks": list(compose_networks.get("networks", {}).keys())}
        # ports_dict = {"ports": []}
        ports_dict_rqd = {
            "ports": OverrideArray(
                [
                    f"{CONFIG_PARENT.OPENCUE_CUEBOT_GRPC_RQD_PORT_HOST}:{CONFIG_PARENT.OPENCUE_CUEBOT_GRPC_RQD_PORT_CONTAINER}",
                ]
            ),
        }
        # ports_dict_cuebot = {
        #     "ports": OverrideArray(
        #         [
        #             f"{CONFIG_PARENT.OPENCUE_CUEBOT_GRPC_CUE_PORT_HOST}:{CONFIG_PARENT.OPENCUE_CUEBOT_GRPC_CUE_PORT_CONTAINER}",
        #         ]
        #     ),
        # }
        # ports_dict_db = {
        #     "ports": OverrideArray(
        #         [
        #             f"{CONFIG_PARENT.OPENCUE_DB_PORT_HOST}:{CONFIG_PARENT.OPENCUE_DB_PORT_CONTAINER}",
        #         ]
        #     ),
        # }
    elif "network_mode" in compose_networks:
        network_dict = {"network_mode": compose_networks["network_mode"]}

    docker_compose_git_repository = pathlib.Path(
        clone_repository.joinpath("docker-compose.yml")
    )

    # opencue_db_dir_host = CONFIG.OPENCUE_DB_INSTALL_DESTINATION_expanded

    # opencue_db_dir_host.mkdir(parents=True, exist_ok=True)
    # context.log.info(f"Directory {opencue_db_dir_host.as_posix()} created.")

    container_prefix = "opencue"

    service_name_db = "db"
    container_name_db, _ = get_docker_compose_names(
        context=context,
        service_name=f"{container_prefix}-{service_name_db}",
        landscape_id=env.get("LANDSCAPE", "default"),
        domain_lan=config_engine.openstudiolandscapes__domain_lan,
    )
    # container_name_db = "--".join(
    #     [f"{container_prefix}-{service_name_db}", env.get("LANDSCAPE", "default")]
    # )
    host_name_db = ".".join(
        [
            f"{container_prefix}-{service_name_db}",
            # Todo
            #  - [ ] For some reason, if the db hostname is suffixed with
            #        the domain name, flyway can't reach it.
            #        Hence, comment this out here.
            #  - [ ] Maybe try to understand the differences in Docker between
            #        - hostname
            #        - domain
            #        - subdomain.domain
            #        - hostname.subdomain.domain
            #        etc.
            # env["OPENSTUDIOLANDSCAPES__DOMAIN_LAN"],
        ]
    )
    # volumes_db = [
    #     f"{opencue_db_dir_host.as_posix()}:/var/lib/postgresql/data:rw",
    # ]

    # _volume_relative_db = []
    #
    # for v in volumes_db:
    #
    #     host, container = v.split(":", maxsplit=1)
    #
    #     volume_dir_host_rel_path = get_relative_path_via_common_root(
    #         context=context,
    #         path_src=docker_compose_git_repository,  # Probably because the root docker-compose is the one in the Git repo
    #         path_dst=pathlib.Path(host),
    #         path_common_root=pathlib.Path(env["DOT_LANDSCAPES"]),
    #     )
    #
    #     _volume_relative_db.append(
    #         f"{volume_dir_host_rel_path.as_posix()}:{container}",
    #     )

    service_name_flyway = "flyway"
    container_name_flyway, host_name_flyway = get_docker_compose_names(
        context=context,
        service_name=f"{container_prefix}-{service_name_flyway}",
        landscape_id=env.get("LANDSCAPE", "default"),
        domain_lan=config_engine.openstudiolandscapes__domain_lan,
    )
    # container_name_flyway = "--".join(
    #     [f"{container_prefix}-{service_name_flyway}", env.get("LANDSCAPE", "default")]
    # )
    # host_name_flyway = ".".join(
    #     [
    #         service_name_flyway,
    #         env["OPENSTUDIOLANDSCAPES__DOMAIN_LAN"],
    #     ]
    # )

    service_name_cuebot = "cuebot"
    container_name_cuebot, host_name_cuebot = get_docker_compose_names(
        context=context,
        service_name=f"{container_prefix}-{service_name_cuebot}",
        landscape_id=env.get("LANDSCAPE", "default"),
        domain_lan=config_engine.openstudiolandscapes__domain_lan,
    )
    # container_name_cuebot = "--".join(
    #     [f"{container_prefix}-{service_name_cuebot}", env.get("LANDSCAPE", "default")]
    # )
    # host_name_cuebot = ".".join(
    #     [
    #         service_name_cuebot,
    #         env["OPENSTUDIOLANDSCAPES__DOMAIN_LAN"],
    #     ]
    # )

    service_name_rqd = "rqd"
    container_name_rqd, host_name_rqd = get_docker_compose_names(
        context=context,
        service_name=f"{container_prefix}-{service_name_rqd}",
        landscape_id=env.get("LANDSCAPE", "default"),
        domain_lan=config_engine.openstudiolandscapes__domain_lan,
    )
    # container_name_rqd = "--".join(
    #     [f"{container_prefix}-{service_name_rqd}", env.get("LANDSCAPE", "default")]
    # )
    # host_name_rqd = ".".join(
    #     [
    #         service_name_rqd,
    #         env["OPENSTUDIOLANDSCAPES__DOMAIN_LAN"],
    #     ]
    # )
    volumes_rqd = [
        f"{prepare_volumes['logs']}:/tmp/rqd/logs:rw",
        f"{prepare_volumes['shots']}:/tmp/rqd/shots:rw",
    ]

    _volume_relative_rqd = []

    for v in volumes_rqd:

        host, container = v.split(":", maxsplit=1)

        volume_dir_host_rel_path = get_relative_path_via_common_root(
            context=context,
            path_src=docker_compose_git_repository,  # Probably because the root docker-compose is the one in the Git repo
            path_dst=pathlib.Path(host),
            path_common_root=pathlib.Path(env["DOT_LANDSCAPES"]),
        )

        _volume_relative_rqd.append(
            f"{volume_dir_host_rel_path.as_posix()}:{container}",
        )

    docker_dict_override = {
        # "networks": compose_networks.get("networks", []),
        "services": {
            service_name_db: {
                "container_name": container_name_db,
                "hostname": host_name_db,
                "domainname": config_engine.openstudiolandscapes__domain_lan,
                # "environment": {
                #     "POSTGRES_DB": CONFIG.OPENCUE_DB_PGDATABASE,
                #     "POSTGRES_PASSWORD": CONFIG.OPENCUE_DB_PGPASSWORD,
                #     "POSTGRES_USER": CONFIG.OPENCUE_DB_PGUSER,
                # },
                # "volumes": [
                #     # *_volume_relative_db,
                # ],
                # **copy.deepcopy(network_dict),
                # **copy.deepcopy(ports_dict_db),
            },
            service_name_flyway: {
                "container_name": container_name_flyway,
                "hostname": host_name_flyway,
                "domainname": config_engine.openstudiolandscapes__domain_lan,
                # "environment": {
                #     "PGHOST": CONFIG.OPENCUE_DB_PGHOST,
                #     "PGDATABASE": CONFIG.OPENCUE_DB_PGDATABASE,
                #     "PGPASSWORD": CONFIG.OPENCUE_DB_PGPASSWORD,
                #     "PGUSER": CONFIG.OPENCUE_DB_PGUSER,
                #     "PGPORT": str(CONFIG.OPENCUE_DB_PORT_CONTAINER),
                # },
                # **copy.deepcopy(network_dict),
                # "networks": [
                #     "mongodb",
                #     "repository",
                # ],
            },
            service_name_cuebot: {
                "container_name": container_name_cuebot,
                "hostname": host_name_cuebot,
                "domainname": config_engine.openstudiolandscapes__domain_lan,
                # This might not be very helpful as a health check
                # but a health check seems mandatory for rqd to be
                # dependent on this service
                # "healthcheck": {
                #     "test": [
                #         "CMD",
                #         "pidof",
                #         "java",
                #     ],
                #     "interval": "10s",
                #     "timeout": "2s",
                #     "retries": "3",
                # },
                # "environment": {
                #     "CUE_FRAME_LOG_DIR": "/tmp/rqd/logs",
                # },
                # Todo:
                #  - [ ] Need to find out whether `ports` Override
                #  also overrides the exports in the source ayon-docker-compose.yml
                #  "exports": OverrideArray([]),
                # "ports": OverrideArray(
                #     [
                #         f"{env.get('AYON_PORT_HOST')}:{env.get('AYON_PORT_CONTAINER')}",
                #     ]
                # ),
                # **copy.deepcopy(network_dict),
                # **copy.deepcopy(ports_dict_cuebot),
            },
            service_name_rqd: {
                "container_name": container_name_rqd,
                "hostname": host_name_rqd,
                "domainname": config_engine.openstudiolandscapes__domain_lan,
                "environment": {
                    "PYTHONUNBUFFERED": "1",
                    # Todo:
                    #  - [x] use fqdn instead of just hostname?
                    #        host_name_cuebot is fqdn
                    #  - [ ] use grpc port? testing...
                    "CUEBOT_HOSTNAME": f"{host_name_cuebot}",
                },
                "restart": DockerComposePolicies.RESTART_POLICY.ALWAYS.value,
                "volumes": [
                    *_volume_relative_rqd,
                ],
                **copy.deepcopy(network_dict),
                **copy.deepcopy(ports_dict_rqd),
            },
        },
    }

    if CONFIG_PARENT.OPENCUE_CUEBOT_USE_PREBUILT_DOCKER_IMAGE:
        docker_dict_override["services"][service_name_cuebot][
            "image"
        ] = CONFIG_PARENT.OPENCUE_CUEBOT_PREBUILT_DOCKER_IMAGE
        # docker_dict_override["services"][service_name_scheduler][
        #     "image"
        # ] = CONFIG.OPENCUE_SCHEDULER_DOCKER_IMAGE

    # make sure only RQD gets propagated
    # !reset db, cuebot, flyway
    if CONFIG.OPENCUE_WORKER_DEPLOY_RQD_ONLY:
        docker_dict_override["services"][service_name_rqd]["depends_on"] = ResetNull(docker_dict_override["services"][service_name_rqd]["depends_on"])
        docker_dict_override["services"][service_name_db] = ResetNull(docker_dict_override["services"][service_name_db])
        docker_dict_override["services"][service_name_cuebot] = ResetNull(docker_dict_override["services"][service_name_cuebot])
        docker_dict_override["services"][service_name_flyway] = ResetNull(docker_dict_override["services"][service_name_flyway])
        context.log.info(f"{docker_dict_override['services'] = }")

    if "networks" in compose_networks:
        network_dict = copy.deepcopy(compose_networks)
    else:
        network_dict = {}

    docker_compose_override = CONFIG.docker_compose_override_expanded

    docker_compose_override.parent.mkdir(parents=True, exist_ok=True)

    with open(docker_compose_git_repository, "r") as fr:
        # Just load is as a str to be able to use it as a MetadataValue
        # (also shows comments of the original yml which is insightful)
        # No post processing for now
        docker_yaml_repository: str = fr.read()

    docker_yaml_override: str = yaml.dump(docker_dict_override)

    with open(docker_compose_override, "w") as fw:
        fw.write(docker_yaml_override)

    # Write compose override to disk here to be able to reference
    # it in the following step.
    # It seems that it's necessary to apply overrides in
    # include: path

    # Convert absolute paths in `include` to
    # relative ones
    DOCKER_COMPOSE = CONFIG.docker_compose_expanded
    DOCKER_COMPOSE.parent.mkdir(parents=True, exist_ok=True)

    rel_paths = []
    dot_landscapes = pathlib.Path(env["DOT_LANDSCAPES"])

    # Todo:
    #  - [x] find a better way to implement relpath with `from` and `via`
    #  - [x] externalize
    for path in [
        docker_compose_git_repository,
        docker_compose_override,
    ]:
        rel_path = get_relative_path_via_common_root(
            context=context,
            path_src=DOCKER_COMPOSE,
            path_dst=pathlib.Path(path),
            path_common_root=dot_landscapes,
        )

        rel_paths.append(rel_path.as_posix())

    docker_dict_include = {
        "include": [
            {
                "path": rel_paths,
            },
        ],
    }

    docker_yaml_include = yaml.dump(docker_dict_include)

    # Write docker-compose.yaml
    with open(DOCKER_COMPOSE, mode="w", encoding="utf-8") as fw:
        fw.write(docker_yaml_include)

    yield Output(docker_dict_include)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(docker_dict_include),
            "docker_yaml_repository": MetadataValue.md(
                f"```yaml\n{docker_yaml_repository}\n```"
            ),
            "docker_yaml_override": MetadataValue.md(
                f"```yaml\n{docker_yaml_override}\n```"
            ),
            "path_docker_yaml_override": MetadataValue.path(docker_compose_override),
            # Todo: "cmd_docker_run": MetadataValue.path(cmd_list_to_str(cmd_docker_run)),
        },
    )
