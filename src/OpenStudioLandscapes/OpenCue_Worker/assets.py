# pylint: disable=line-too-long,invalid-name
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
from OpenStudioLandscapes.engine.common_assets import (
    cmd,
    compose,
    docker_compose_graph,
    feature,
    feature_out,
    group_in,
    group_out,
)
from OpenStudioLandscapes.engine.env.configurable_resources.config_engine import ConfigEngineConfigurableResource
from OpenStudioLandscapes.engine.base.configurable_resources.rez_resource import RezConfigurableResource
from OpenStudioLandscapes.engine.constants import (
    ASSET_HEADER_BASE,
)
from OpenStudioLandscapes.engine.enums import (
    DockerComposePolicies,
)
from OpenStudioLandscapes.engine.utils import (
    get_docker_compose_names,
    get_relative_path_via_common_root,
)
from OpenStudioLandscapes.engine.utils.docker.compose_dicts import (
    get_network_dicts,
)
from OpenStudioLandscapes.OpenCue import ASSET_HEADER as ASSET_HEADER_FEATURE_IN

# Override default ConfigParent
from OpenStudioLandscapes.OpenCue.config.models import Config as ConfigParent

from OpenStudioLandscapes.OpenCue_Worker import (
    ASSET_HEADER,
    config,
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

cmd: AssetsDefinition = cmd.get_feature__cmd(
    ASSET_HEADER=ASSET_HEADER,
)

CONFIG: AssetsDefinition = feature.get_feature__CONFIG(
    ASSET_HEADER=ASSET_HEADER,
    CONFIG_STR=config.models.CONFIG_STR,
    search_model_of_type=config.models.Config,
)

feature_in: AssetsDefinition = group_in.get_feature_in(
    ASSET_HEADER=ASSET_HEADER,
    ASSET_HEADER_BASE=ASSET_HEADER_BASE,
    ASSET_HEADER_FEATURE_IN=ASSET_HEADER_FEATURE_IN,
)

group_out: AssetsDefinition = group_out.get_group_out(
    ASSET_HEADER=ASSET_HEADER,
)


docker_compose_graph: AssetsDefinition = docker_compose_graph.get_docker_compose_graph(
    ASSET_HEADER=ASSET_HEADER,
)


compose: AssetsDefinition = compose.get_compose(
    ASSET_HEADER=ASSET_HEADER,
)


feature_out_v2: AssetsDefinition = feature_out.get_feature_out_v2(
    ASSET_HEADER=ASSET_HEADER,
)


# Produces
# - feature_in_parent
# - CONFIG_PARENT
# if ConfigParent is or type FeatureBaseModel
feature_in_parent: Union[AssetsDefinition, None] = group_in.get_feature_in_parent(
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
    CONFIG: config.models.Config,  # pylint: disable=redefined-outer-name
) -> Generator[
    Output[Dict[str, Dict[str, Dict[str, str]]]] | AssetMaterialization, None, None
]:

    env: Dict = CONFIG.env

    # Possible overrides:
    # https://github.com/AcademySoftwareFoundation/OpenCue/blob/master/rqd/rqd/rqpy
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
        "CONFIG": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG"]),
        ),
        "CONFIG_PARENT": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "CONFIG_PARENT"]),
        ),
        "compose_networks": AssetIn(
            AssetKey([*ASSET_HEADER["key_prefix"], "compose_networks"]),
        ),
        "build_docker_image_rqd": AssetIn(
            AssetKey(
                [*ASSET_HEADER_FEATURE_IN["key_prefix"], "build_docker_image_rqd"]
            ),
        ),
        "compose_opencue_base": AssetIn(
            AssetKey([*ASSET_HEADER_FEATURE_IN["key_prefix"], "compose_opencue_base"]),
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
    config_ConfigEngineConfigurableResource: ConfigEngineConfigurableResource,
    config_RezConfigurableResource: RezConfigurableResource,
    CONFIG: config.models.Config,  # pylint: disable=redefined-outer-name
    CONFIG_PARENT: ConfigParent,  # pylint: disable=redefined-outer-name
    compose_networks: Dict,  # pylint: disable=redefined-outer-name
    build_docker_image_rqd: Dict,  # pylint: disable=redefined-outer-name
    compose_opencue_base: Dict,  # pylint: disable=redefined-outer-name
) -> Generator[Output[Dict] | AssetMaterialization, None, None]:
    """ """

    env: Dict = CONFIG.env

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
            domain_lan=config_ConfigEngineConfigurableResource.openstudiolandscapes__domain_lan,
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
            # https://github.com/AcademySoftwareFoundation/OpenCue/blob/ce61412b723c4020a6676842e175a228b3026daa/rqd/rqd/rqpy#L188
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

        service_name_cuebot = CONFIG_PARENT.opencue_cuebot
        container_name_cuebot, host_name_cuebot = get_docker_compose_names(
            context=context,
            service_name=service_name_cuebot,
            landscape_id=env.get("LANDSCAPE", "default"),
            domain_lan=config_ConfigEngineConfigurableResource.openstudiolandscapes__domain_lan,
        )

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
                    # Todo
                    #  - [ ] Check Rez paths etc.
                    #        volumes:
                    #        - /data/share/rez-packages/packages:/data/share/rez-packages/packages
                    #        - /home/michael/.rez/packages/int:/home/michael/.rez/packages/int
                    #        - /home/michael/packages:/home/michael/packages
                    #        - /data/share:/data/share:rw
                    #        [...]
                    *_volume_relative,
                    *config_ConfigEngineConfigurableResource.global_bind_volumes,
                    *CONFIG.local_bind_volumes,
                    *config_RezConfigurableResource.REZ_PACKAGES_PATH_VOL,
                }
            )
        }

        # service_name = "rqd"
        # container_name, host_name = get_docker_compose_names(
        #     context=context,
        #     service_name=f"opencue-{service_name}",
        #     landscape_id=env.get("LANDSCAPE", "default"),
        #     domain_lan=config_ConfigEngineConfigurableResource.openstudiolandscapes__domain_lan,
        # )

        compose_rqd_base = compose_opencue_base.get("services", {}).get("rqd", {})
        compose_rqd_base.pop("profiles", None)
        compose_rqd_base.pop("build", None)
        compose_rqd_base.pop("depends_on", None)

        docker_dict["services"].update(
            {
                service_name: {
                    **compose_rqd_base,
                    "image": "%s%s:%s"
                    % (
                        build_docker_image_rqd["image_prefixes"],
                        build_docker_image_rqd["image_name"],
                        build_docker_image_rqd["image_tags"][0],
                    ),
                    "container_name": container_name,
                    # To have a unique, dynamic hostname, we simply must not
                    # specify it.
                    # https://forums.docker.com/t/docker-compose-set-container-name-and-hostname-dynamicaly/138259/2
                    # https://shantanoo-desai.github.io/posts/technology/hostname-docker-container/
                    # "hostname": host_name,
                    "domainname": config_ConfigEngineConfigurableResource.openstudiolandscapes__domain_lan,
                    "environment": {
                        "TZ": config_ConfigEngineConfigurableResource.tz,
                        "PYTHONUNBUFFERED": "1",
                        # Todo:
                        #  - [ ] use fqdn instead of just hostname?
                        # OpenStudioLandscapes-OpenCue/OpenStudioLandscapes_OpenCue__clone_repository/repos/OpenCue/rqd/rqd/rqpy
                        # "CUEBOT_HOSTNAME": f"{CONFIG_PARENT.opencue_str}-cuebot.{config_ConfigEngineConfigurableResource.openstudiolandscapes__domain_lan}",
                        "OPENRQD__GRPC__CUEBOT_ENDPOINTS": f"{host_name_cuebot}:{CONFIG_PARENT.OPENCUE_CUEBOT_GRPC_CUE_PORT_HOST}",
                        "OPENRQD__MACHINE__USE_IP_AS_HOSTNAME": False,
                        # Todo
                        #  - [ ] Is this still necessary now that we *can*
                        #        specify the worker hostname at runtime?
                        "HOSTNAME": "${HOSTNAME}${HOSTNAME:+-}%s-%s"
                        % (CONFIG.compose_scope, container_name),
                        **config_ConfigEngineConfigurableResource.global_environment_variables,
                        **CONFIG.local_environment_variables,
                        **config_RezConfigurableResource.REZ_ENVIRONMENT,
                    },
                    **copy.deepcopy(volumes_dict),
                    **copy.deepcopy(network_dict),
                    **copy.deepcopy(ports_dict),
                },
            },
        )

    context.log.debug(docker_dict)

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
