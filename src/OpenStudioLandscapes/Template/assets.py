import copy
import json
import pathlib
import shutil
import textwrap
import urllib.parse

import time
from typing import Generator

import yaml

from dagster import (
    AssetExecutionContext,
    AssetIn,
    AssetKey,
    AssetMaterialization,
    MetadataValue,
    Output,
    asset,
    AssetsDefinition,
)

from OpenStudioLandscapes.engine.base.assets import KEY_BASE
from OpenStudioLandscapes.engine.constants import *

from OpenStudioLandscapes.engine.enums import *
from OpenStudioLandscapes.engine.utils import *
from OpenStudioLandscapes.engine.utils.docker.whales import *

from OpenStudioLandscapes.engine.base.ops import (
    op_compose,
    op_docker_compose_graph,
    op_group_out,
)

from OpenStudioLandscapes.<Your_New_Feature>.constants import *


@asset(
    **ASSET_HEADER,
    ins={
        "group_in": AssetIn(
            AssetKey([*KEY_BASE, "group_out"])
        ),
    },
    deps=[
        AssetKey([*ASSET_HEADER['key_prefix'], "constants"])
    ],
)
def env(
    context: AssetExecutionContext,
    group_in: dict,  # pylint: disable=redefined-outer-name
) -> Generator[Output[dict] | AssetMaterialization, None, None]:

    env_in = copy.deepcopy(group_in["env"])

    env_in.update(ENVIRONMENT)

    env_in.update(
        {
            "COMPOSE_SCOPE": COMPOSE_SCOPE,
        },
    )

    yield Output(env_in)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(env_in),
            "ENVIRONMENT": MetadataValue.json(ENVIRONMENT),
        },
    )


@asset(
    **ASSET_HEADER,
)
def pip_packages(
    context: AssetExecutionContext,
) -> Generator[Output[list] | AssetMaterialization, None, None]:
    """ """

    _pip_packages: list = []

    yield Output(_pip_packages)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(_pip_packages),
        },
    )


@asset(
    **ASSET_HEADER,
)
def apt_packages(
    context: AssetExecutionContext,
) -> Generator[Output[dict] | AssetMaterialization, None, None]:
    """ """

    _apt_packages = {}

    _apt_packages["list_a"] = [
        "git",
        "ca-certificates",
        "htop",
        "file",
        "tzdata",
        "curl",
        "wget",
        "ffmpeg",
        "xvfb",
        "libegl1",
        "libsm6",
        "libsm6",
        "libglu1-mesa",
        "libxss1",
    ]

    _apt_packages["list_b"] = [
        "build-essential",
        "pkg-config",
        "zlib1g-dev",
        "libncurses5-dev",
        "libgdbm-dev",
        "libnss3-dev",
        "libssl-dev",
        "libreadline-dev",
        "libffi-dev",
        "libsqlite3-dev",
        "libbz2-dev",
        "iproute2",
    ]

    yield Output(_apt_packages)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(_apt_packages),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "env": AssetIn(
            AssetKey([*KEY, "env"]),
        ),
        "group_in": AssetIn(
            AssetKey([*KEY_BASE, "group_out"])
        ),
        "apt_packages": AssetIn(
            AssetKey([*KEY, "apt_packages"]),
        ),
        "pip_packages": AssetIn(
            AssetKey([*KEY, "pip_packages"]),
        ),
    },
)
def build_docker_image(
    context: AssetExecutionContext,
    env: dict,  # pylint: disable=redefined-outer-name
    group_in: dict,  # pylint: disable=redefined-outer-name
    apt_packages: dict[str, list[str]],  # pylint: disable=redefined-outer-name
    pip_packages: list,  # pylint: disable=redefined-outer-name
) -> Generator[Output[dict] | AssetMaterialization, None, None]:
    """ """

    build_base_image_data: dict = group_in["docker_image"]
    build_base_docker_config: DockerConfig = group_in["docker_config"]

    if build_base_docker_config.value["docker_push"]:
        build_base_parent_image_prefix: str = build_base_image_data["image_prefix_full"]
    else:
        build_base_parent_image_prefix: str = build_base_image_data["image_prefix_local"]

    build_base_parent_image_name: str = build_base_image_data["image_name"]
    build_base_parent_image_tags: list = build_base_image_data["image_tags"]

    docker_file = pathlib.Path(
        env["DOT_LANDSCAPES"],
        env.get("LANDSCAPE"),
        f"{GROUP}__{'__'.join(KEY)}",
        "__".join(context.asset_key.path),
        "Dockerfiles",
        "Dockerfile",
    )

    docker_file.parent.mkdir(parents=True, exist_ok=True)

    image_name = get_image_name(context=context)
    image_prefix_local = parse_docker_image_path(
        docker_config=build_base_docker_config,
        prepend_registry=False,
    )
    image_prefix_full = parse_docker_image_path(
        docker_config=build_base_docker_config,
        prepend_registry=True,
    )

    # @formatter:off
    extra_files = {
        "MyFile.txt": env.get(f"PATH_TO_LOCAL_MY_FILE_TXT"),
    }
    # @formatter:on

    tags = [
        env.get('LANDSCAPE', str(time.time())),
    ]

    apt_install_str_list_a: str = get_apt_install_str(
        apt_install_packages=apt_packages["list_a"],
    )

    apt_install_str_list_b: str = get_apt_install_str(
        apt_install_packages=apt_packages["list_b"],
    )

    pip_install_str: str = get_pip_install_str(pip_install_packages=pip_packages)

    if bool(extra_files):

        docker_payload = ".payload"
        tmpdir = docker_file.parent / docker_payload
        tmpdir.mkdir(exist_ok=True, parents=True)

        # Todo
        #  copy_str: str = get_copy_str(
        #      temp_dir=tmpdir,
        #      copy_packages=files,
        #      mode=755,
        #  )

        # @formatter:off
        docker_file_str = textwrap.dedent(
            """
            # {auto_generated}
            # {dagster_url}
            FROM {parent_image} AS {image_name}
            LABEL authors="{AUTHOR}"

            ARG DEBIAN_FRONTEND=noninteractive
    
            ENV CONTAINER_TIMEZONE={TIMEZONE}
            ENV SET_CONTAINER_TIMEZONE=true

            SHELL ["/bin/bash", "-c"]

            RUN apt-get update && apt-get upgrade -y

            {apt_install_str_list_a}
    
            {apt_install_str_list_b}

            {pip_install_str}

            WORKDIR /workdir

            # copy_str

            # RUN commands
            # [...]
        
            # COPY ./{tmpdir}/<FILE> .
            # RUN chmod 644 FILE
            # RUN chown user:group FILE

            RUN apt-get clean

            ENTRYPOINT []
        """
        ).format(
            # copy_str=copy_str,
            tmpdir=pathlib.Path(tmpdir).name,
            apt_install_str_list_a=apt_install_str_list_a,
            apt_install_str_list_b=apt_install_str_list_b,
            pip_install_str=pip_install_str.format(
                **env,
            ),
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

        for key, value in extra_files.items():
            shutil.copyfile(
                src=value,
                dst=pathlib.Path(tmpdir) / key,
            )

    else:

        # @formatter:off
        docker_file_str = textwrap.dedent(
            """
            # {auto_generated}
            # {dagster_url}
            FROM {parent_image} AS {image_name}
            LABEL authors="{AUTHOR}"
    
            ARG DEBIAN_FRONTEND=noninteractive
    
            ENV CONTAINER_TIMEZONE={TIMEZONE}
            ENV SET_CONTAINER_TIMEZONE=true
    
            RUN apt-get update && apt-get upgrade -y

            {apt_install_str_list_a}
    
            {apt_install_str_list_b}
    
            {pip_install_str}
    
            WORKDIR /workdir
    
            # RUN commands
            # [...]
        
            RUN apt-get clean
    
            ENTRYPOINT []
        """
        ).format(
            apt_install_str_list_a=apt_install_str_list_a,
            apt_install_str_list_b=apt_install_str_list_b,
            pip_install_str=pip_install_str.format(
                **env,
            ),
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

    image_data = {
        "image_name": image_name,
        "image_prefix_local": image_prefix_local,
        "image_prefix_full": image_prefix_full,
        "image_tags": tags,
        "image_parent": copy.deepcopy(build_base_image_data),
    }

    tags_list: list = docker_build(
        context=context,
        docker_config=build_base_docker_config,
        docker_file=docker_file,
        context_path=docker_file.parent,
        docker_use_cache=DOCKER_USE_CACHE,
        image_data=image_data,
    )

    yield Output(image_data)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(image_data),
            "tags_list": MetadataValue.json(tags_list),
            "docker_file": MetadataValue.md(
                f"```shell\n{docker_file_content}\n```"
            ),
            "env": MetadataValue.json(env),
        },
    )


@asset(
    **ASSET_HEADER,
)
def compose_networks(
    context: AssetExecutionContext,
) -> Generator[
    Output[dict[str, dict[str, dict[str, str]]]] | AssetMaterialization, None, None]:

    compose_network_mode = ComposeNetworkMode.DEFAULT

    if compose_network_mode == ComposeNetworkMode.DEFAULT:
        docker_dict = {
            "networks": {
                "template": {
                    "name": "network_template",
                },
            },
        }

    else:
        docker_dict = {
            "network_mode": compose_network_mode.value,
        }

    docker_yaml = yaml.dump(docker_dict)

    yield Output(docker_dict)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(docker_dict),
            "compose_network_mode": MetadataValue.text(compose_network_mode.value),
            "docker_dict": MetadataValue.md(
                f"```json\n{json.dumps(docker_dict, indent=2)}\n```"
            ),
            "docker_yaml": MetadataValue.md(f"```shell\n{docker_yaml}\n```"),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "env": AssetIn(
            AssetKey([*KEY, "env"]),
        ),
        "build": AssetIn(
            AssetKey([*KEY, "build_docker_image"]),
        ),
        "compose_networks": AssetIn(
            AssetKey([*KEY, "compose_networks"]),
        ),
    },
)
def compose_template(
    context: AssetExecutionContext,
    build: dict,  # pylint: disable=redefined-outer-name
    env: dict,  # pylint: disable=redefined-outer-name
    compose_networks: dict,  # pylint: disable=redefined-outer-name
) -> Generator[Output[dict] | AssetMaterialization, None, None]:
    """ """

    network_dict = {}
    ports_dict = {}

    if "networks" in compose_networks:
        network_dict = {
            "networks": list(compose_networks.get("networks", {}).keys())
        }
        ports_dict = {
            "ports": [
                f"{env.get('PORT_HOST')}:{env.get('PORT_CONTAINER')}",
            ]
        }
    elif "network_mode" in compose_networks:
        network_dict = {
            "network_mode": compose_networks.get("network_mode")
        }

    volumes_dict = {
        "volumes": [],
    }

    service_name = "Your_New_Feature"
    container_name = service_name
    host_name = ".".join([service_name, env["ROOT_DOMAIN"]])

    docker_dict = {
        "services": {
            service_name: {
                "container_name": container_name,
                "hostname":  host_name,
                "domainname": env.get("ROOT_DOMAIN"),
                "restart": "always",
                **[
                    {
                        "image": "docker.io/template/template",
                    },
                    {
                        "image": f"{build['image_prefix_full']}{build['image_name']}:{build['image_tags'][0]}",
                    },
                ][1],
                **copy.deepcopy(volumes_dict),
                **copy.deepcopy(network_dict),
                **copy.deepcopy(ports_dict),
                # "environment": {
                # },
                # "healthcheck": {
                # },
                # "command": [
                # ],
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
            # Todo: "cmd_docker_run": MetadataValue.path(cmd_list_to_str(cmd_docker_run)),
        },
    )


@asset(
    **ASSET_HEADER,
    ins={
        "compose_Your_New_Feature": AssetIn(
            AssetKey([*KEY, "compose_Your_New_Feature"]),
        ),
    },
)
def compose_maps(
    context: AssetExecutionContext,
    **kwargs,  # pylint: disable=redefined-outer-name
) -> Generator[Output[list[dict]] | AssetMaterialization, None, None]:

    ret = list(kwargs.values())

    context.log.info(ret)

    yield Output(ret)

    yield AssetMaterialization(
        asset_key=context.asset_key,
        metadata={
            "__".join(context.asset_key.path): MetadataValue.json(ret),
        },
    )


compose = AssetsDefinition.from_op(
    op_compose,
    tags_by_output_name={
        "compose": {
            "compose": "third_party",
        },
    },
    group_name=GROUP,
    key_prefix=KEY,
    keys_by_input_name={
        "compose_networks": AssetKey(
            [*KEY, "compose_networks"]
        ),
        "compose_maps": AssetKey(
            [*KEY, "compose_maps"]
        ),
    },
)


group_out = AssetsDefinition.from_op(
    op_group_out,
    can_subset=True,
    group_name=GROUP,
    tags_by_output_name={
        "group_out": {
            "group_out": "third_party",
        },
    },
    key_prefix=KEY,
    keys_by_input_name={
        "compose": AssetKey(
            [*KEY, "compose"]
        ),
        "env": AssetKey(
            [*KEY, "env"]
        ),
        "group_in": AssetKey(
            [*KEY_BASE, "group_out"]
        ),
    },
)


docker_compose_graph = AssetsDefinition.from_op(
    op_docker_compose_graph,
    group_name=GROUP,
    key_prefix=KEY,
    keys_by_input_name={
        "group_out": AssetKey(
            [*KEY, "group_out"]
        ),
        "compose_project_name": AssetKey(
            [*KEY, "compose_project_name"]
        ),
    },
)
