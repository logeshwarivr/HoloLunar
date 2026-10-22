import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from PIL import Image

DEM = r"D:\HoloLunar\Data\dem_faustini_v2.tif"   # <-- put your real filename here

with rasterio.open("faustini_cpr_clip.tif") as ref:
    shape, transform, crs = ref.shape, ref.transform, ref.crs
    profile = ref.profile

with rasterio.open(DEM) as src:
    print("DEM CRS:", src.crs, "| res:", src.res, "| nodata:", src.nodata)
    dem = np.full(shape, np.nan, dtype="float32")
    reproject(
        source=rasterio.band(src, 1), destination=dem,
        src_nodata=src.nodata, dst_nodata=np.nan,
        dst_transform=transform, dst_crs=crs,
        resampling=Resampling.bilinear,
    )

valid = np.isfinite(dem)
print("DEM valid fraction:", valid.mean())
print("elevation min/max (m):", np.nanmin(dem), np.nanmax(dem))

profile.update(dtype="float32", nodata=np.nan)
with rasterio.open("faustini_dem_clip.tif", "w", **profile) as dst:
    dst.write(dem, 1)

# 16-bit heightmap for Unity (keep the min/max for the report)
lo, hi = np.nanmin(dem), np.nanmax(dem)
h16 = np.where(valid, (dem - lo) / (hi - lo) * 65535, 0).astype("uint16")
Image.fromarray(h16).resize((2048, 2048), Image.BILINEAR).save("web_heightmap_real.png")
print("heightmap scale: 0 =", lo, "m, 65535 =", hi, "m")