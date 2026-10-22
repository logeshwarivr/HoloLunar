import json
from pathlib import Path
import numpy as np, rasterio
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parent.parent
RAW, CROPS = ROOT / "data" / "raw", ROOT / "data" / "crops"
CROPS.mkdir(parents=True, exist_ok=True)
N, SIZE, SEED = 10, 512, 0

SOURCES = {
    "lola":   dict(file="lola.tif",   scale=0.5, offset=0.0, pixel_m=120.0, kind="dem", invalid=None),
    "copdem": dict(file="copdem.tif", scale=1.0, offset=0.0, pixel_m=30.0,  kind="dem", invalid=None),
    "s1vv":   dict(file="s1_vv.tif",  scale=1.0, offset=0.0, pixel_m=10.0,  kind="sar", invalid=0),
}
meta = {}
for name, cfg in SOURCES.items():
    path = RAW / cfg["file"]
    if not path.exists():
        print(f"skip {name}: {path} not found"); continue
    for old in CROPS.glob(f"{name}_*.npy"): old.unlink()
    rng = np.random.default_rng(SEED); saved = 0; tries = 0
    with rasterio.open(path) as src:
        h, w, nodata = src.height, src.width, src.nodata
        if h <= SIZE or w <= SIZE:
            print(f"skip {name}: raster smaller than {SIZE} x {SIZE}"); continue
        while saved < N and tries < 5000:
            tries += 1
            r, c = int(rng.integers(0, h - SIZE)), int(rng.integers(0, w - SIZE))
            a = src.read(1, window=Window(c, r, SIZE, SIZE)).astype(np.float32)
            bad = ~np.isfinite(a)
            if nodata is not None: bad |= (a == nodata)
            if cfg["invalid"] is not None: bad |= (a == cfg["invalid"])
            if bad.mean() > 0.001: continue
            a = a * cfg["scale"] + cfg["offset"]
            if cfg["kind"] == "sar":
                lo, hi = np.percentile(a, [0.5, 99.5]); a = np.clip(a, lo, hi)
            if a.max() - a.min() < 1e-6: continue
            np.save(CROPS / f"{name}_{saved:02d}.npy", a.astype(np.float32)); saved += 1
    meta[name] = dict(pixel_m=cfg["pixel_m"], kind=cfg["kind"])
    print(f"{name}: saved {saved} crops")
json.dump(meta, open(CROPS / "meta.json", "w"), indent=1)
