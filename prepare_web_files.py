import rasterio
import numpy as np
from PIL import Image

# Load DEM
with rasterio.open("D:/HoloLunar/Data/dem_faustini_v2.tif") as src:
    dem = src.read(1).astype(np.float32)
    dem = np.nan_to_num(dem, nan=np.nanmin(dem))

# Downsample if very large (keeps browser fast)
from scipy.ndimage import zoom
max_size = 512
if dem.shape[0] > max_size:
    scale = max_size / dem.shape[0]
    dem = zoom(dem, scale)

# Normalize DEM to 0-255 and save as heightmap image
dem_norm = (dem - dem.min()) / (dem.max() - dem.min())
heightmap = (dem_norm * 255).astype(np.uint8)
Image.fromarray(heightmap).save("D:/HoloLunar/Data/web_heightmap.png")

# Load confidence map, resize to match
conf_img = Image.open("D:/HoloLunar/Data/ice_confidence_faustini_SIMULATED.png").convert("L")
conf_img = conf_img.resize((heightmap.shape[1], heightmap.shape[0]))
conf_img.save("D:/HoloLunar/Data/web_confidence.png")

print("Web-ready files created: web_heightmap.png, web_confidence.png")
print("Heightmap size:", heightmap.shape)