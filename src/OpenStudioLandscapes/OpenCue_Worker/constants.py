__all__ = [
    "ASSET_HEADER",
]

from OpenStudioLandscapes.OpenCue_Worker import dist

# Todo
#  - [ ] fix this naive replacement logic
GROUP = dist.name.replace("-", "_")
KEY = [GROUP]

ASSET_HEADER = {
    "group_name": GROUP,
    "key_prefix": KEY,
}
