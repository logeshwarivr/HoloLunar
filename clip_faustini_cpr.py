import numpy as np, rasterio
from rasterio.windows import Window
from pyproj import CRS, Transformer
from PIL import Image

P = r"D:\HoloLunar\ch2_sar_ndxl_20250630mpcpspwest_d_fp_xxx\data\derived\20250630\ch2_sar_ndxl_20250630mpcpspwest_d_cpr_xx_fp_xx_xxx.tif"
LAT, LON, HALF_KM = -87.3, 77.0, 30

with rasterio.open(P) as src:
    print("CRS:", src.crs, "| res:", src.res, "| nodata:", src.nodata)
    crs = CRS.from_wkt(src.crs.to_wkt())
    x, y = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True).transform(LON, LAT)
    r, c = src.index(x, y)
    h = int(HALF_KM * 1000 / src.res[0])
    win = Window(c - h, r - h, 2 * h, 2 * h)
    cpr = src.read(1, window=win).astype("float32")
    prof = src.profile | {"height": 2*h, "width": 2*h,
                          "transform": src.window_transform(win), "compress": "deflate"}

if src.nodata is not None:
    cpr[cpr == src.nodata] = np.nan
cpr[~np.isfinite(cpr)] = np.nan
v = cpr[np.isfinite(cpr)]
print("valid %:", 100 * v.size / cpr.size)
print("percentiles 2/50/98/99.9:", np.percentile(v, [2, 50, 98, 99.9]))
print("fraction CPR>1:", (v > 1).mean())

with rasterio.open("faustini_cpr_clip.tif", "w", **prof) as dst:
    dst.write(cpr, 1)

# Unity texture: 0 to 2 mapped to 0-255, nodata = 0
png = np.nan_to_num(np.clip(cpr, 0, 2) / 2 * 255).astype("uint8")
Image.fromarray(png).resize((2048, 2048), Image.BILINEAR).save("web_confidence_real.png")