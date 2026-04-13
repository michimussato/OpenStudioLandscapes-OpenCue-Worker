from dagster import Definitions
from OpenStudioLandscapes.engine.base.assets import group_out_base
from OpenStudioLandscapes.OpenCue.assets import (
    build_docker_image,
    feature_out_v2,
)

from OpenStudioLandscapes.OpenCue_Worker.definitions import assets_base

# The visualized DAG is cleaner when using `build_docker_image_spec`
# instead of `build_docker_image.specs` - yet they should be
# equivalent. However, using `build_docker_image_spec` requires
# its Materializable Asset to be a `multi_asset`

assets_external = []
assets_external.extend(group_out_base.specs)
assets_external.extend(build_docker_image.specs)
assets_external.extend(feature_out_v2.specs)


defs = Definitions(
    assets=[
        *assets_base,
        *assets_external,
    ],
)
