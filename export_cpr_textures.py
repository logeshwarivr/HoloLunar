import numpy as np, rasterio
from PIL import Image

N = 2400   # output size in pixels (the clip itself is 2400 x 2400)

with rasterio.open("faustini_cpr_clip.tif") as s:
    cpr = s.read(1)

valid = np.isfinite(cpr)
lo, hi = 0.0, 1.5                      # CPR 1.0 lands at ~67% brightness
norm = np.clip((np.nan_to_num(cpr) - lo) / (hi - lo), 0, 1)
gray = np.where(valid, norm * 255, 0).astype("uint8")

Image.fromarray(gray).resize((N, N), Image.BILINEAR).save("web_confidence_real.png")
Image.fromarray((valid * 255).astype("uint8")).resize((N, N), Image.NEAREST).save("web_valid_mask.png")
Image.fromarray(((np.nan_to_num(cpr) > 1) * 255).astype("uint8")).resize((N, N), Image.NEAREST).save("web_cpr_gt1_mask.png")

print("valid:", valid.mean(), "CPR>1 (of valid):", (cpr[valid] > 1).mean())