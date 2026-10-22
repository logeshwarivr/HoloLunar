import numpy as np, rasterio
from PIL import Image

with rasterio.open("faustini_cpr_clip.tif") as s:
    print("bounds:", s.bounds, "| size:", s.width, "x", s.height)
    cpr = s.read(1)

valid = np.isfinite(cpr)
g = np.where(valid, np.clip(cpr / 1.5, 0, 1) * 255, 0).astype("uint8")
rgb = np.stack([g, g, g], -1)
rgb[valid & (cpr > 1)] = [255, 60, 60]       # CPR > 1 in red
rgb[~valid] = [0, 0, 90]                      # nodata in blue
h, w = g.shape
rgb[h//2-1:h//2+2, :] = [255, 255, 0]         # crosshair at the clip center
rgb[:, w//2-1:w//2+2] = [255, 255, 0]
Image.fromarray(rgb).resize((1024, 1024), Image.NEAREST).save("preview_cpr.png")