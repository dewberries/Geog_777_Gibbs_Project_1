from pathlib import Path

# Configuration settings for the Cancer–Nitrate Analysis App
APP_TITLE = "Cancer & Nitrate Analysis App"

# Data paths
WELLS_SHP = Path("data/inputs/wells/well_nitrate.shp")
TRACTS_SHP = Path("data/inputs/cancer_tracts/cancer_tracts.shp")

# Fields
NITRATE_FIELD = "nitr_ran"
CANCER_FIELD = "canrate"
TRACT_ID_FIELD = "GEOID10"

# Defaults (user only changes k + output folder)
DEFAULT_K = 2.0
CELL_SIZE = 250
NEIGHBORS = 15

# Output settings
OVERWRITE_OUTPUTS = True

# Map PNG export settings
MAP_DPI = 150
MAP_SIZE = (8.5, 6.0)