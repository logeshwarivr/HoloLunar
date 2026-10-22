import numpy as np, rasterio
from PIL import Image

with rasterio.open("faustini_dem_clip.tif") as s:
    dem = s.read(1)

lo, hi = np.nanmin(dem), np.nanmax(dem)
norm = np.where(np.isfinite(dem), (dem - lo) / (hi - lo), 0)
N = 2049                                   # Unity terrain needs 2^n + 1
img = Image.fromarray((norm * 65535).astype("uint16")).resize((N, N), Image.BILINEAR)
np.asarray(img, dtype="<u2").tofile("faustini_height_2049.r16")
print("height range (m):", hi - lo, "| lo:", lo, "| hi:", hi)