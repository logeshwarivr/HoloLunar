import rasterio
import numpy as np
from PIL import Image

dem_path = "D:/HoloLunar/Data/dem_faustini_v2.tif"
output_tif = "D:/HoloLunar/Data/ice_confidence_faustini_SIMULATED.tif"
output_png = "D:/HoloLunar/Data/ice_confidence_faustini_SIMULATED.png"

# ---- LOAD DEM (elevation) ----
with rasterio.open(dem_path) as src:
    dem = src.read(1).astype(np.float32)
    profile = src.profile

# ---- SIMPLE PHYSICALLY-MOTIVATED PROXY ----
# Real DFSAR ice detection depends on radar scattering, not elevation directly.
# As a placeholder ONLY: assume deeper, low-elevation crater floors (likely
# permanently shadowed) have higher simulated ice-likelihood.
# THIS IS NOT REAL SCIENTIFIC DATA - clearly state this in your report.

elev_min = np.nanmin(dem)
elev_max = np.nanmax(dem)
normalized_depth = 1 - ((dem - elev_min) / (elev_max - elev_min))  # deeper = higher score

# Add some smooth random variation so it doesn't look artificially perfect
np.random.seed(42)
noise = np.random.normal(0, 0.05, dem.shape)
confidence = np.clip(normalized_depth * 0.8 + noise, 0, 1)

# ---- SAVE ----
profile.update(dtype=rasterio.float32, count=1)
with rasterio.open(output_tif, "w", **profile) as dst:
    dst.write(confidence, 1)

img = (confidence * 255).astype(np.uint8)
Image.fromarray(img).save(output_png)

print("SIMULATED confidence map saved — replace with real DFSAR data if PRADAN approves.")