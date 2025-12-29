import copy
import enum
import pathlib
import shutil
import textwrap
import urllib.parse
from typing import Any, Dict, Generator, List, Union

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
from OpenStudioLandscapes.engine.config.models import ConfigEngine
from OpenStudioLandscapes.engine.constants import *
from OpenStudioLandscapes.engine.enums import *
from OpenStudioLandscapes.engine.utils import *
from OpenStudioLandscapes.engine.utils.docker.compose_dicts import *

# Override default ConfigParent
from OpenStudioLandscapes.OpenCue.config.models import Config as ConfigParent
from OpenStudioLandscapes.OpenCue.constants import (
    ASSET_HEADER as ASSET_HEADER_FEATURE_IN,
)

from OpenStudioLandscapes.OpenCue_Worker import dist
from OpenStudioLandscapes.OpenCue_Worker.config.models import CONFIG_STR, Config
from OpenStudioLandscapes.OpenCue_Worker.constants import *

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


# compose_scope_group__cmd: AssetsDefinition = get_compose_scope_group__cmd(
#     ASSET_HEADER=ASSET_HEADER,
# )

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

    compose_network_mode = DockerComposePolicies.NETWORK_MODE.HOST

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
        "CONFIG_PARENT": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG_PARENT"]),
        ),
        "compose_networks": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose_networks"]),
        ),
    },
    description=textwrap.dedent(
        """
        Based on
        - [docker-compose.yml](https://github.com/AcademySoftwareFoundation/OpenCue/blob/master/docker-compose.yml)
        
        Reference:
        ```
          rqd:
            image: opencue/rqd
            environment:
              - PYTHONUNBUFFERED=1
              - CUEBOT_HOSTNAME=cuebot
            depends_on:
              cuebot:
                condition: service_healthy
            links:
              - cuebot
            ports:
              - "8444:8444"
            volumes:
              - /tmp/rqd/logs:/tmp/rqd/logs
              - /tmp/rqd/shots:/tmp/rqd/shots
        ```
        """
    ),
)
def compose_rqd_worker(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
    CONFIG_PARENT: ConfigParent,  # pylint: disable=redefined-outer-name
    compose_networks: Dict,  # pylint: disable=redefined-outer-name
) -> Generator[Output[Dict] | AssetMaterialization, None, None]:
    """ """

    env: Dict = CONFIG.env

    config_engine: ConfigEngine = CONFIG.config_engine

    service_name_base = CONFIG.opencue_rqd_worker

    docker_dict = {"services": {}}

    for i in range(CONFIG.opencue_worker_NUM_SERVICES):
        service_name = (
            f"{service_name_base}-{str(i+1).zfill(CONFIG.opencue_worker_PADDING)}"
        )
        container_name, _ = get_docker_compose_names(
            context=context,
            service_name=service_name,
            landscape_id=env.get("LANDSCAPE", "default"),
            domain_lan=config_engine.openstudiolandscapes__domain_lan,
        )

        network_dict = {}
        ports_dict = {}

        if "networks" in compose_networks:
            network_dict = {
                "networks": list(compose_networks.get("networks", {}).keys())
            }
            ports_dict = {"ports": []}
        elif "network_mode" in compose_networks:
            network_dict = {"network_mode": compose_networks["network_mode"]}

        # Prepare Volumes

        storage = pathlib.Path(CONFIG.opencue_worker_storage_expanded).joinpath(
            service_name
        )

        rqd_conf = storage.joinpath("conf", "rqd.conf")

        rqd_conf.parent.mkdir(parents=True, exist_ok=True)

        # @formatter:off
        rqd_conf_str = textwrap.dedent(
            """\
            # {auto_generated}
            # {dagster_url}
            # Reference
            # https://github.com/AcademySoftwareFoundation/OpenCue/blob/ce61412b723c4020a6676842e175a228b3026daa/rqd/rqd/rqconstants.py#L188
            [Override]
            USE_NIMBY_PYNPUT=false
            RQD_USE_IP_AS_HOSTNAME=false
            OVERRIDE_HOSTNAME={hostname}
            """
        ).format(
            auto_generated=f"AUTO-GENERATED by Dagster Asset {'__'.join(context.asset_key.path)}",
            dagster_url=urllib.parse.quote(
                f"http://localhost:3000/asset-groups/{'%2F'.join(context.asset_key.path)}",
                safe=":/%",
            ),
            hostname=service_name,
        )
        # @formatter:on

        rqd_conf.write_text(rqd_conf_str)

        volume_logs = storage / "logs"
        volume_logs.mkdir(parents=True, exist_ok=True)
        volume_shots = storage / "shots"
        volume_shots.mkdir(parents=True, exist_ok=True)

        volumes_dict = {
            "volumes": [
                f"{rqd_conf.as_posix()}:/etc/opencue/rqd.conf:ro",
                f"{volume_logs.as_posix()}:/tmp/rqd/logs:rw",
                f"{volume_shots.as_posix()}:/tmp/rqd/shots:rw",
            ]
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
            ]
        }

        # service_name = "rqd"
        # container_name, host_name = get_docker_compose_names(
        #     context=context,
        #     service_name=f"opencue-{service_name}",
        #     landscape_id=env.get("LANDSCAPE", "default"),
        #     domain_lan=config_engine.openstudiolandscapes__domain_lan,
        # )

        docker_dict["services"].update(
            {
                service_name: {
                    "image": "docker.io/opencue/rqd",
                    "container_name": container_name,
                    # To have a unique, dynamic hostname, we simply must not
                    # specify it.
                    # https://forums.docker.com/t/docker-compose-set-container-name-and-hostname-dynamicaly/138259/2
                    # https://shantanoo-desai.github.io/posts/technology/hostname-docker-container/
                    # "hostname": host_name,
                    "domainname": config_engine.openstudiolandscapes__domain_lan,
                    "restart": DockerComposePolicies.RESTART_POLICY.ALWAYS.value,
                    "environment": {
                        "PYTHONUNBUFFERED": "1",
                        # Todo:
                        #  - [ ] use fqdn instead of just hostname?
                        # OpenStudioLandscapes-OpenCue/OpenStudioLandscapes_OpenCue__clone_repository/repos/OpenCue/rqd/rqd/rqconstants.py
                        "CUEBOT_HOSTNAME": f"{CONFIG_PARENT.opencue_str}-cuebot.{config_engine.openstudiolandscapes__domain_lan}",
                    },
                    **copy.deepcopy(volumes_dict),
                    **copy.deepcopy(network_dict),
                    **copy.deepcopy(ports_dict),
                },
            },
        )

    docker_yaml = yaml.dump(docker_dict)

    yield Output(docker_dict)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(docker_dict),
            "docker_yaml": MetadataValue.md(f"```yaml\n{docker_yaml}\n```"),
            # "rqd_conf": MetadataValue.path(rqd_conf),
            # "rqd_conf_str": MetadataValue.md(f"```\n{rqd_conf_str}\n```"),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "compose_rqd_worker": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose_rqd_worker"]),
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
    ins={},
)
def cmd_extend(
    context: AssetExecutionContext,
) -> Generator[Output[List[Any]] | AssetMaterialization | Any, Any, None]:

    ret = ["--detach"]

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
        # "CONFIG_PARENT": AssetIn(
        #     AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG_PARENT"]),
        # ),
        "compose": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose"]),
        ),
    },
)
def cmd_append(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
    # CONFIG_PARENT: ConfigParent,  # pylint: disable=redefined-outer-name
    compose: Dict,  # pylint: disable=redefined-outer-name,
) -> Generator[Output[Dict[str, List[Any]]] | AssetMaterialization | Any, Any, None]:

    env: Dict = CONFIG.env

    ret = {"cmd": [], "exclude_from_quote": []}

    compose_services = list(compose["services"].keys())

    # Example cmd:
    # /usr/bin/docker compose --file /home/michael/git/repos/OpenStudioLandscapes/.landscapes/2025-04-08-10-45-09-df78673952cc4499a80407d91bd404f4/Deadline_10_2_Worker__Deadline_10_2_Worker/Deadline_10_2_Worker__group_out/docker_compose/docker-compose.yml --project-name 2025-04-08-10-45-09-df78673952cc4499a80407d91bd404f4-worker up --detach --remove-orphans && sudo nsenter --target $(docker inspect -f '{{ .State.Pid }}' deadline-10-2-worker-001) --uts hostname "$(hostname -f)-nice-hack"

    # cmd_docker_compose_up.extend(
    #     [
    #         # needs to be detached in order to get to do sudo
    #         "--detach",
    #     ]
    # )

    exclude_from_quote = []

    cmd_docker_compose_set_dynamic_hostnames = []

    # Transform container hostnames
    # - deadline-10-2-worker-001...nnn
    # - deadline-10-2-pulse-worker-001...nnn
    # into
    # - $(hostname)-deadline-10-2-worker-001...nnn
    # - $(hostname)-deadline-10-2-pulse-worker-001...nnn
    for service_name in compose_services:

        target_worker = (
            "$($(which docker) inspect -f '{{ .State.Pid }}' %s)"
            % ".".join([service_name, env.get("LANDSCAPE", "default")])
        )
        hostname_worker = f"$(hostname)-{service_name}"

        exclude_from_quote.extend(
            [
                target_worker,
                hostname_worker,
            ]
        )

        cmd_docker_compose_set_dynamic_hostname_worker = [
            shutil.which("sudo"),
            shutil.which("nsenter"),
            "--target",
            target_worker,
            "--uts",
            "hostname",
            hostname_worker,
        ]

        # Reference:
        # /usr/bin/docker --config /home/michael/git/repos/OpenStudioLandscapes/.landscapes/2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa/OpenStudioLandscapes_Base__OpenStudioLandscapes_Base/OpenStudioLandscapes_Base__docker_config_json compose --progress plain --file /home/michael/git/repos/OpenStudioLandscapes/.landscapes/2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa/Deadline_10_2_Worker__Deadline_10_2_Worker/Deadline_10_2_Worker__DOCKER_COMPOSE/docker_compose/docker-compose.yml --project-name 2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa-worker up --remove-orphans --detach && /usr/bin/sudo /usr/bin/nsenter --target $(docker inspect -f '{{ .State.Pid }}' deadline-10-2-worker-001--2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa) --uts hostname $(hostname)-deadline-10-2-worker-001 && /usr/bin/sudo /usr/bin/nsenter --target $(docker inspect -f '{{ .State.Pid }}' deadline-10-2-pulse-worker-001--2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa) --uts hostname $(hostname)-deadline-10-2-pulse-worker-001 \
        #     && /usr/bin/docker --config /home/michael/git/repos/OpenStudioLandscapes/.landscapes/2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa/OpenStudioLandscapes_Base__OpenStudioLandscapes_Base/OpenStudioLandscapes_Base__docker_config_json compose --progress plain --file /home/michael/git/repos/OpenStudioLandscapes/.landscapes/2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa/Deadline_10_2_Worker__Deadline_10_2_Worker/Deadline_10_2_Worker__DOCKER_COMPOSE/docker_compose/docker-compose.yml --project-name 2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa-worker logs --follow
        # Current:
        # Pre
        # /usr/bin/docker --config /home/michael/git/repos/OpenStudioLandscapes/.landscapes/2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa/OpenStudioLandscapes_Base__OpenStudioLandscapes_Base/OpenStudioLandscapes_Base__docker_config_json compose --progress plain --file /home/michael/git/repos/OpenStudioLandscapes/.landscapes/2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa/Deadline_10_2_Worker__Deadline_10_2_Worker/Deadline_10_2_Worker__DOCKER_COMPOSE/docker_compose/docker-compose.yml --project-name 2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa-worker up --remove-orphans --detach && /usr/bin/sudo /usr/bin/nsenter --target '$(docker inspect -f '"'"'{{ .State.Pid }}'"'"' deadline-10-2-pulse-worker-001--2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa)' --uts hostname '$(hostname)-deadline-10-2-pulse-worker-001' && /usr/bin/sudo /usr/bin/nsenter --target '$(docker inspect -f '"'"'{{ .State.Pid }}'"'"' deadline-10-2-worker-001--2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa)' --uts hostname '$(hostname)-deadline-10-2-worker-001'
        # Post
        #                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   && /usr/bin/sudo /usr/bin/nsenter --target $(docker inspect -f '{{ .State.Pid }}' deadline-10-2-pulse-worker-001--2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa) --uts hostname $(hostname)-deadline-10-2-pulse-worker-001 && /usr/bin/sudo /usr/bin/nsenter --target $(docker inspect -f '{{ .State.Pid }}' deadline-10-2-worker-001--2025-07-23-00-51-15-1afae50517c5453b95c518ee0cd8e0aa) --uts hostname $(hostname)-deadline-10-2-worker-001

        cmd_docker_compose_set_dynamic_hostnames.extend(
            [
                "&&",
                *cmd_docker_compose_set_dynamic_hostname_worker,
            ]
        )

    ret["cmd"].extend(cmd_docker_compose_set_dynamic_hostnames)
    ret["exclude_from_quote"].extend(
        [
            "$(which docker)",
            "&&",
            ";",
            *exclude_from_quote,
        ]
    )

    yield Output(ret)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(ret),
        },
    )
