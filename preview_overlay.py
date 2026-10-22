import numpy as np, rasterio
from PIL import Image

with rasterio.open("faustini_dem_clip.tif") as s:
    dem = s.read(1)
with rasterio.open("faustini_cpr_clip.tif") as s:
    cpr = s.read(1)

dy, dx = np.gradient(np.nan_to_num(dem, nan=np.nanmean(dem)), 25)
shade = np.clip(0.5 + (dx - dy) * 0.5, 0, 1)        # simple relief shading
g = (shade * 255).astype("uint8")
rgb = np.stack([g, g, g], -1)
hot = np.isfinite(cpr) & (cpr > 1)
rgb[hot] = [255, 40, 40]
Image.fromarray(rgb).resize((1024, 1024)).save("preview_overlay.png")
print("CPR>1 pixels:", int(hot.sum()))