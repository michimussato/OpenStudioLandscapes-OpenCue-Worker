from dagster import (
    Definitions,
    load_assets_from_modules,
)

import OpenStudioLandscapes.<Your_New_Feature>.assets
import OpenStudioLandscapes.<Your_New_Feature>.constants


assets = load_assets_from_modules(
    modules=[OpenStudioLandscapes.<Your_New_Feature>.assets],
)

constants = load_assets_from_modules(
    modules=[OpenStudioLandscapes.<Your_New_Feature>.constants],
)


defs = Definitions(
    assets=[
        *assets,
        *constants,
    ],
)
