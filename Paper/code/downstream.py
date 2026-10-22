# Slope test for hybrid, wavelet, JPEG2000 (matched bitrate) and SZ3 (if pysz is installed).
# Local:  python downstream.py
# Colab:  python downstream.py crops downstream.csv      (needs compress_lib.py beside this file)
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from compress_lib import *
try:
    from pysz import sz, szConfig, szErrorBoundMode
    HAVE_SZ = True
except Exception:
    HAVE_SZ = False

ROOT = Path(__file__).resolve().parent.parent
CROPS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "crops"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "results" / "downstream.csv"
mf = next(iter(CROPS.rglob("meta.json")), None)
meta = json.load(open(mf)) if mf else {}
DEFAULT = {"lola": dict(pixel_m=120.0, kind="dem"), "copdem": dict(pixel_m=30.0, kind="dem")}
EPS = [0.002, 0.01, 0.05]
RATIOS = [1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512]
HYB_RATIOS = [r for r in RATIOS if r >= 3]
THR = 10.0
print("SZ3 available:", HAVE_SZ)

def sz3_codec(x, eps):
    cfg = szConfig(); cfg.errorBoundMode = szErrorBoundMode.ABS; cfg.absErrorBound = float(eps)
    comp, _ = sz.compress(np.ascontiguousarray(x, dtype=np.float32), cfg)
    return sz.decompress(comp, np.float32, x.shape)[0], 8 * comp.nbytes

rows = []
for path in sorted(CROPS.rglob("*.npy")):
    crop = path.stem; ds = crop.rsplit("_", 1)[0]
    info = meta.get(ds) or DEFAULT.get(ds)
    if not info or info.get("kind") != "dem": continue
    p = info["pixel_m"]; a = np.load(path).astype(np.float64); lo, hi = a.min(), a.max(); span = hi - lo
    x = ((a - lo) / span).astype(np.float32); s0 = slope_deg(a, p)[1:-1, 1:-1]
    print(crop, flush=True)
    base = {r: jp2_roundtrip(x, r) for r in RATIOS}

    def score(codec, eps, y, bits):
        s1 = slope_deg(y.astype(np.float64) * span + lo, p)[1:-1, 1:-1]; e = np.abs(s1 - s0)
        bound = float(np.degrees(np.sqrt(2) * eps * span / p))
        rows.append(dict(dataset=ds, crop=crop, codec=codec, eps=eps, eps_m=eps * span, bpp=bits / x.size,
                         max_slope_err_deg=e.max(), mean_slope_err_deg=e.mean(),
                         class_flip_rate=float(((s0 > THR) != (s1 > THR)).mean()),
                         bound_deg=bound, bound_deg_capped=min(bound, 90.0)))
    for eps in EPS:
        yh, bh = min((hybrid_from_base(x, base[r][0], base[r][1], eps) for r in HYB_RATIOS), key=lambda t: t[1])
        score("hybrid", eps, yh, bh)
        yw, bw, _ = wavelet_codec(x, eps); score("wavelet", eps, yw, bw)
        r = min(RATIOS, key=lambda r: abs(base[r][1] - bh)); score("jp2_matched_bpp", eps, base[r][0], base[r][1])
        if HAVE_SZ:
            ys, bs = sz3_codec(x, eps); score("sz3", eps, ys, bs)

D = pd.DataFrame(rows)
D["bound_ok"] = D.max_slope_err_deg <= D.bound_deg + 1e-6
OUT.parent.mkdir(parents=True, exist_ok=True); D.to_csv(OUT, index=False)
G = D.groupby(["dataset", "codec", "eps"]).agg(
    eps_m=("eps_m", "mean"), bpp=("bpp", "mean"), max_slope_err_deg=("max_slope_err_deg", "mean"),
    mean_slope_err_deg=("mean_slope_err_deg", "mean"), class_flip_rate=("class_flip_rate", "mean"),
    bound_deg_capped=("bound_deg_capped", "mean"), crops_within_bound=("bound_ok", "sum"), n=("bound_ok", "size"))
print(G.round(4).to_string()); print("saved", OUT)
