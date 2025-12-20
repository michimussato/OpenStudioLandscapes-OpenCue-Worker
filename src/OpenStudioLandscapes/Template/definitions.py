from dagster import (
    Definitions,
    load_assets_from_modules,
)

import OpenStudioLandscapes.Template.assets

assets = load_assets_from_modules(
    modules=[OpenStudioLandscapes.Template.assets],
)


defs = Definitions(
    assets=[
        *assets,
    ],
)
