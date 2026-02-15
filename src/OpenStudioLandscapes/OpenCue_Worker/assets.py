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
from OpenStudioLandscapes.engine.config.models import ConfigEngine, DockerConfigModel
from OpenStudioLandscapes.engine.constants import *
from OpenStudioLandscapes.engine.enums import *
from OpenStudioLandscapes.engine.link.models import OpenStudioLandscapesFeatureIn
from OpenStudioLandscapes.engine.policies.retry import build_docker_image_retry_policy
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


# Overridden locally
# cmd: AssetsDefinition = get_feature__cmd(
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

    # Possible overrides:
    # https://github.com/AcademySoftwareFoundation/OpenCue/blob/master/rqd/rqd/rqconstants.py
    # rqd does weird things in order to get the hostname
    # https://github.com/AcademySoftwareFoundation/OpenCue/blob/ce61412b723c4020a6676842e175a228b3026daa/rqd/rqd/rqutil.py#L207
    # In HOST mode, it resolves to the hostname of the host instead
    # of the container
    # HOST is therefore a bad idea
    #
    # [root@lenovo-opencue-rqd-worker opencue]# cat /etc/hostname
    # eb48b21e945e
    # [root@lenovo-opencue-rqd-worker opencue]# hostname
    # lenovo-opencue-rqd-worker
    # [root@lenovo-opencue-rqd-worker opencue]# echo $HOSTNAME  # I set this manually
    # lenovo-worker.opencue-rqd-worker.2026-01-20_00-42-28__clumsy-peaceful-volcano-sprite
    # [root@lenovo-opencue-rqd-worker opencue]# python3
    # Python 3.9.20 (main, Aug 29 2025, 17:46:29)
    # [GCC 8.5.0 20210514 (Red Hat 8.5.0-28)] on linux
    # Type "help", "copyright", "credits" or "license" for more information.
    # >>> from rqd.rqutil import getHostname
    # WARNING:root:Loading config /etc/opencue/rqd.conf
    # WARNING:root:CUEBOT_HOSTNAME: opencue-cuebot.openstudiolandscapes.lan
    # >>> getHostname()
    # 'eb48b21e945e'
    #
    # Furthermore:
    # OVERRIDE_HOSTNAME=hello-world.worker.opencue-rqd-worker.2026-01-20_00-42-28__clumsy-peaceful-volcano-sprite
    # results in hostname = hello-world
    # With override:
    # [root@lenovo-opencue-rqd-worker opencue]# python3
    # Python 3.9.20 (main, Aug 29 2025, 17:46:29)
    # [GCC 8.5.0 20210514 (Red Hat 8.5.0-28)] on linux
    # Type "help", "copyright", "credits" or "license" for more information.
    # >>> from rqd.rqutil import getHostname
    # WARNING:root:Loading config /etc/opencue/rqd.conf
    # WARNING:root:CUEBOT_HOSTNAME: opencue-cuebot.openstudiolandscapes.lan
    # >>> getHostname()
    # 'hello-world-worker.opencue-rqd-worker.2026-01-20_00-42-28__clumsy-peaceful-volcano-sprite'
    #
    # So: OVERRIDE_HOSTNAME must not contain periods (splitting). Period.
    #
    # However: respect max segment length!
    # 45 chars is the hard limit it seems
    # if longer, the worker will just not show up in CueGUI
    #
    # [root@lenovo-opencue-rqd-worker opencue]# python3
    # Python 3.9.20 (main, Aug 29 2025, 17:46:29)
    # [GCC 8.5.0 20210514 (Red Hat 8.5.0-28)] on linux
    # Type "help", "copyright", "credits" or "license" for more information.
    # >>> from rqd.rqutil import getHostname
    # WARNING:root:Loading config /etc/opencue/rqd.conf
    # WARNING:root:CUEBOT_HOSTNAME: opencue-cuebot.openstudiolandscapes.lan
    # >>> getHostname()
    # 'hello-world-worker-opencue-rqd-worker-2026-01-20_00-42-28__clumsy-peaceful-volcano-sprite'

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
    context.log.debug(f"{docker_image = }")
    # docker_image = {'image_name': 'openstudiolandscapes_base_build_docker_image', 'image_prefixes': '', 'image_tags': ['2025-11-17-01-26-31-05a9b85aa33b47ffa7dfb21a28ca24ab'], 'image_parent': {}}

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
    hosts_sh = {
        # "AWSPortalLink.run": CONFIG.deadline_10_2_installer_aws_portal_link_expanded,
        "hosts.sh": CONFIG.rqd_hosts_sh_expanded,
        # "DeadlineRepository.run": CONFIG.deadline_10_2_installer_deadline_repository_expanded,
    }
    # @formatter:on

    payload = docker_file.parent / "payload"
    payload.mkdir(parents=True, exist_ok=True)

    copy_str: str = get_copy_str(
        temp_dir=payload,
        copy_packages=hosts_sh,
        mode=755,
    )

    # apt_install_str: str = get_apt_install_str(
    #     apt_install_packages=CONFIG.apt_packages,
    # )
    #
    # pip_install_str: str = get_pip_install_str(
    #     pip_install_packages=CONFIG.pip_packages,
    # )

    # @formatter:off
    docker_file_str = textwrap.dedent("""\
        # {auto_generated}
        # {dagster_url}
        FROM {parent_image} AS {image_name}
        LABEL authors="{AUTHOR}"
        
        SHELL ["/bin/bash", "-c"]
        
        WORKDIR /

        {copy_str}
        
        WORKDIR /opt/opencue
        
        # Default ENTRYPOINT of {parent_image} is
        # ENTRYPOINT set -e && rqd
        # Now the /hosts.sh part is a big hack to be able
        # (at least to some extent) to control the hostname
        # of rqd on the target machine. OpenCue is pretty 
        # messed up in terms of applying the hostname itself
        # to rqd and how it's displayed in CueCommander.
        # We modify the default image here and mess with 
        # /etc/hosts file.
        ENTRYPOINT set -e && /hosts.sh && rqd
        CMD []
        """).format(
        copy_str=copy_str,
        auto_generated=f"AUTO-GENERATED by Dagster Asset {'__'.join(context.asset_key.path)}",
        dagster_url=urllib.parse.quote(
            f"http://localhost:3000/asset-groups/{'%2F'.join(context.asset_key.path)}",
            safe=":/%",
        ),
        image_name=image_name,
        # Todo: this won't work as expected if len(tags) > 1
        parent_image="docker.io/opencue/rqd",
        **env,
    )
    # @formatter:on

    with open(docker_file, "w") as fw:
        fw.write(docker_file_str)

    with open(docker_file, "r") as fr:
        docker_file_content = fr.read()

    # Copy Deadline Installer(s) to build context
    for key, value in hosts_sh.items():
        if not value.exists():
            context.log.error(f"File {value.as_posix()} does not exist")
        context.log.debug(f"{value = }")
        context.log.debug(f"{payload / key = }")
        shutil.copyfile(
            src=value,
            dst=payload / key,
        )

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
            "docker_file": MetadataValue.md(f"```yaml\n{docker_file_content}\n```"),
            "logs": MetadataValue.json(logs),
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
        "build": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "build_docker_image"]),
        ),
    },
    description=textwrap.dedent("""
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
        """),
)
def compose_rqd_worker(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
    CONFIG_PARENT: ConfigParent,  # pylint: disable=redefined-outer-name
    compose_networks: Dict,  # pylint: disable=redefined-outer-name
    build: Dict,  # pylint: disable=redefined-outer-name
) -> Generator[Output[Dict] | AssetMaterialization, None, None]:
    """ """

    env: Dict = CONFIG.env

    config_engine: ConfigEngine = CONFIG.config_engine

    service_name_base = CONFIG.opencue_rqd_worker

    docker_dict = {"services": {}}

    for i in range(CONFIG.opencue_worker_NUM_SERVICES):

        if CONFIG.opencue_worker_NUM_SERVICES == 1:
            # Ignore incrementation
            service_name = f"{service_name_base}"

        else:
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
        rqd_conf_str = textwrap.dedent("""\
            # {auto_generated}
            # {dagster_url}
            # Reference
            # https://github.com/AcademySoftwareFoundation/OpenCue/blob/ce61412b723c4020a6676842e175a228b3026daa/rqd/rqd/rqconstants.py#L188
            [Override]
            USE_NIMBY_PYNPUT=false
            RQD_USE_IP_AS_HOSTNAME=false
            # OVERRIDE_HOSTNAME={hostname}
            """).format(
            auto_generated=f"AUTO-GENERATED by Dagster Asset {'__'.join(context.asset_key.path)}",
            dagster_url=urllib.parse.quote(
                f"http://localhost:3000/asset-groups/{'%2F'.join(context.asset_key.path)}",
                safe=":/%",
            ),
            hostname=f"{CONFIG.compose_scope}.{container_name}",
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
            "volumes": list(
                {
                    *_volume_relative,
                    *config_engine.global_bind_volumes,
                    *CONFIG.local_bind_volumes,
                }
            )
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
                    # "image": "docker.io/opencue/rqd",
                    "image": "%s%s:%s"
                    % (
                        build["image_prefixes"],
                        build["image_name"],
                        build["image_tags"][0],
                    ),
                    "container_name": container_name,
                    # To have a unique, dynamic hostname, we simply must not
                    # specify it.
                    # https://forums.docker.com/t/docker-compose-set-container-name-and-hostname-dynamicaly/138259/2
                    # https://shantanoo-desai.github.io/posts/technology/hostname-docker-container/
                    # "hostname": host_name,
                    "domainname": config_engine.openstudiolandscapes__domain_lan,
                    "restart": DockerComposePolicies.RESTART_POLICY.ALWAYS.value,
                    "environment": {
                        "TZ": CONFIG.tz,
                        "PYTHONUNBUFFERED": "1",
                        # Todo:
                        #  - [ ] use fqdn instead of just hostname?
                        # OpenStudioLandscapes-OpenCue/OpenStudioLandscapes_OpenCue__clone_repository/repos/OpenCue/rqd/rqd/rqconstants.py
                        "CUEBOT_HOSTNAME": f"{CONFIG_PARENT.opencue_str}-cuebot.{config_engine.openstudiolandscapes__domain_lan}",
                        "HOSTNAME": "${HOSTNAME}${HOSTNAME:+-}%s-%s"
                        % (CONFIG.compose_scope, container_name),
                        **config_engine.global_environment_variables,
                        **CONFIG.local_environment_variables,
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
            "rqd_conf": MetadataValue.path(rqd_conf),
            "rqd_conf_str": MetadataValue.md(f"```ini\n{rqd_conf_str}\n```"),
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
        "compose": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose"]),
        ),
    },
)
def cmd_append(
    context: AssetExecutionContext,
    CONFIG: Config,  # pylint: disable=redefined-outer-name
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
    # - ${HOSTNAME}-deadline-10-2-worker-001...nnn
    # - ${HOSTNAME}-deadline-10-2-pulse-worker-001...nnn
    #
    # We do this because the this worker might be running on
    # a machine which hostname we don't know at build time
    # so the machine name needs to be extracted and forwarded
    # to the Docker container.
    # Note: $HOSTNAME is not defined (at least on some OSs)
    # so we have to set it in the "up"-scripts
    #
    #
    # Set /etc/hostname manually
    # /usr/bin/sudo --stdin /usr/bin/nsenter --target "$($(which docker) inspect -f '{{ .State.Pid }}' opencue-rqd-worker.2026-01-20_00-42-28__clumsy-peaceful-volcano-sprite)" --uts --mount bash -c "echo 'Hello-World' | tee /etc/hostname"
    # has no effect
    # because of this stupid OpenCue implementation:
    # [root@lenovo-opencue-rqd-worker opencue]# cat /etc/hostname
    # new_host
    # [root@lenovo-opencue-rqd-worker opencue]# echo $HOSTNAME
    # lenovo-worker.opencue-rqd-worker.2026-01-20_00-42-28__clumsy-peaceful-volcano-sprite
    # [root@lenovo-opencue-rqd-worker opencue]# python3
    # Python 3.9.20 (main, Aug 29 2025, 17:46:29)
    # [GCC 8.5.0 20210514 (Red Hat 8.5.0-28)] on linux
    # Type "help", "copyright", "credits" or "license" for more information.
    # >>> import socket
    # >>> socket.gethostbyname(socket.gethostname())
    # '192.168.80.2'
    # >>> socket.gethostname()
    # 'lenovo-opencue-rqd-worker'
    # >>> from rqd.rqutil import getHostname, getHostIp
    # WARNING:root:Loading config /etc/opencue/rqd.conf
    # WARNING:root:CUEBOT_HOSTNAME: opencue-cuebot.openstudiolandscapes.lan
    # >>> getHostname()
    # '717405c8ec22'
    # >>> socket.gethostbyaddr(getHostIp())
    # ('717405c8ec22.openstudiolandscapes.lan', ['717405c8ec22'], ['192.168.80.2'])
    # >>> socket.getfqdn()
    # '717405c8ec22.openstudiolandscapes.lan'
    # [root@lenovo-opencue-rqd-worker opencue]# cat /etc/hosts
    # 127.0.0.1       localhost
    # ::1     localhost ip6-localhost ip6-loopback
    # fe00::  ip6-localnet
    # ff00::  ip6-mcastprefix
    # ff02::1 ip6-allnodes
    # ff02::2 ip6-allrouters
    # 192.168.80.2    717405c8ec22.openstudiolandscapes.lan 717405c8ec22
    # [root@lenovo-opencue-rqd-worker opencue]#
    #
    # Only Option:
    # edit /etc/hosts file
    #
    # [root@lenovo-opencue-rqd-worker opencue]# cat /etc/hosts
    # 127.0.0.1       localhost
    # ::1     localhost ip6-localhost ip6-loopback
    # fe00::  ip6-localnet
    # ff00::  ip6-mcastprefix
    # ff02::1 ip6-allnodes
    # ff02::2 ip6-allrouters
    # 192.168.80.2    my-new-host
    # [root@lenovo-opencue-rqd-worker opencue]# python3
    # Python 3.9.20 (main, Aug 29 2025, 17:46:29)
    # [GCC 8.5.0 20210514 (Red Hat 8.5.0-28)] on linux
    # Type "help", "copyright", "credits" or "license" for more information.
    # >>> import socket
    # >>> socket.gethostbyname(socket.gethostname())
    # '192.168.80.2'
    # >>> from rqd.rqutil import getHostname, getHostIp
    # WARNING:root:Loading config /etc/opencue/rqd.conf
    # WARNING:root:CUEBOT_HOSTNAME: opencue-cuebot.openstudiolandscapes.lan
    # >>> getHostname()
    # 'my-new-host'
    # >>> socket.gethostbyaddr(getHostIp())
    # ('my-new-host', [], ['192.168.80.2'])
    for service_name in compose_services:

        target_worker = (
            "\"$($(which docker) inspect --format '{{ .State.Pid }}' %s)\""
            % ".".join([service_name, env.get("LANDSCAPE", "default")])
        )
        hostname_worker = f"${{HOSTNAME}}-{service_name}"

        # hostname_worker_truncated = hostname_worker.replace(".", "_")[:45]

        exclude_from_quote.extend(
            [
                target_worker,
                hostname_worker,
                # hostname_worker_truncated,
            ]
        )

        cmd_docker_compose_set_dynamic_hostname_worker = [
            shutil.which("sudo"),
            "--stdin",
            # https://man7.org/linux/man-pages/man1/nsenter.1.html
            shutil.which("nsenter"),
            "--target",
            target_worker,
            "--uts",
            "hostname",
            hostname_worker,
        ]

        # get last line:
        # - tail -n 1 /etc/hosts
        # - sed -n '$p' /etc/hosts
        # sed "s/$(printf '\t')/'\tmynewhost'/g" /etc/hosts
        #  tail -n 1 /etc/hosts | sed "s/$(printf '\t')/\t${HOSTNAME}/g"
        #  tail -n 1 /etc/hosts | sed "s/^$(printf '\t')/'\t${HOSTNAME}'/g"
        # tail -n 1 /etc/hosts | sed "s/\t.*/\t${HOSTNAME}/g"

        # https://collectingwisdom.com/sed-replace-last-line-matching-pattern/
        # tac points.txt | sed '/Mavs/ {s//Lakers/; :loop; n; b loop}' | tac

        # tac /etc/hosts | sed "0,/\t.*/{s/\t.*/\t${HOSTNAME}/g}"
        #                      '         s/\(.*\)-/\1 /'
        # tac /etc/hosts | sed "0,/\t.*/{s/\t.*/\t${HOSTNAME}/g}" | tac > /etc/hosts
        # tac original.txt > temp.txt && mv temp.txt original.txt
        # tac /etc/hosts > /etc/.hosts && cat /etc/.hosts | sed "0,/\t.*/{s/\t.*/\t${HOSTNAME}/g}" | tac > /etc/hosts

        # truncate /etc/hosts
        # https://stackoverflow.com/questions/45125826/delete-everything-after-a-certain-line-in-bash
        # truncate -s `head -6 /etc/hosts | wc -c` /etc/hosts
        # truncate -s $(head -6 /etc/hosts | wc -c) /etc/hosts
        # str_truncate_etc_hosts = "\"truncate -s $(head -5 /etc/hosts | wc -c) /etc/hosts\""
        # tac /etc/hosts > /etc/.hosts && cat /etc/.hosts | sed "0,/\t.*/{s/\t.*/\t${HOSTNAME}/g}" | tac > /etc/hosts
        # str_truncate_etc_hosts = "tac /etc/hosts > /etc/.hosts && cat /etc/.hosts | sed \"0,/\\t.*/{s/\\t.*/\\t$(hostname -f)/g}\" | tac > /etc/hosts"
        #
        # cmd_docker_compose_truncate_etc_hosts = [
        #     shutil.which("sudo"),
        #     "--stdin",
        #     # https://man7.org/linux/man-pages/man1/nsenter.1.html
        #     shutil.which("nsenter"),
        #     "--target",
        #     target_worker,
        #     "--uts",
        #     "--mount",
        #     # "env",
        #     "bash",
        #     "-c",
        #     str_truncate_etc_hosts,
        #     # hostname_worker,
        # ]

        # str_set_etc_hostname = "\"echo %s | tee /etc/hostname\"" % hostname_worker
        #
        # cmd_docker_compose_set_dynamic_etc_hostname_worker = [
        #     shutil.which("sudo"),
        #     "--stdin",
        #     # https://man7.org/linux/man-pages/man1/nsenter.1.html
        #     shutil.which("nsenter"),
        #     "--target",
        #     target_worker,
        #     "--uts",
        #     "--mount",
        #     # "env",
        #     "bash",
        #     "-c",
        #     str_set_etc_hostname,
        #     # hostname_worker,
        # ]

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
                # "&&",
                # *cmd_docker_compose_truncate_etc_hosts,
                # *cmd_docker_compose_set_dynamic_etc_hostname_worker,
            ]
        )

    ret["cmd"].extend(cmd_docker_compose_set_dynamic_hostnames)
    ret["exclude_from_quote"].extend(
        [
            "$(which docker)",
            "&&",
            ";",
            # str_truncate_etc_hosts,
            # str_set_etc_hostname,
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
