import csv, glob, os
from pathlib import Path
import numpy as np
from compress_lib import *

ROOT = Path(__file__).resolve().parent.parent
CROPS, OUT = ROOT / "data" / "crops", ROOT / "results" / "results.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)
EPS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]      # fraction of crop value range
JP2_RATIOS = [1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512]
HYB_RATIOS = [r for r in JP2_RATIOS if r >= 3]              # JPEG2000 base layers tried by the hybrid codec
ZFP_MULTS = [1, 1.5, 2, 3, 4, 6, 8]                         # ZFP tolerance = eps x mult; best one meeting the bound is kept
FIELDS = ["dataset", "crop", "codec", "param", "extra", "bpp", "maxerr", "psnr"]

done = set()
if OUT.exists():
    done = {r["crop"] for r in csv.DictReader(open(OUT))}
new = not OUT.exists()
f = open(OUT, "a", newline=""); wr = csv.DictWriter(f, FIELDS)
if new: wr.writeheader()

for path in sorted(glob.glob(str(CROPS / "*.npy"))):
    crop = os.path.basename(path)[:-4]
    if crop in done: continue
    dataset = crop.rsplit("_", 1)[0]
    a = np.load(path).astype(np.float32); lo, hi = float(a.min()), float(a.max())
    x = ((a - lo) / (hi - lo)).astype(np.float32); N = x.size
    row = lambda codec, param, extra, y, bits: wr.writerow(dict(
        dataset=dataset, crop=crop, codec=codec, param=param, extra=extra, bpp=bits / N,
        maxerr=float(np.abs(x - y).max()), psnr=psnr(x, y)))
    print(crop, flush=True)
    base = {r: jp2_roundtrip(x, r) for r in JP2_RATIOS}
    for r, (y0, b0) in base.items(): row("jp2", r, "", y0, b0)
    for eps in EPS:
        y, bits, m = wavelet_codec(x, eps); assert np.abs(x - y).max() <= eps + 1e-5; row("wavelet", eps, m, y, bits)
        best = None
        for r in HYB_RATIOS:
            y0, b0 = base[r]; yh, bh = hybrid_from_base(x, y0, b0, eps)
            if best is None or bh < best[1]: best = (yh, bh, r)
        assert np.abs(x - best[0]).max() <= eps + 1e-5; row("hybrid", eps, best[2], best[0], best[1])
        bz = None
        for mult in ZFP_MULTS:
            z = zfp_codec(x, eps * mult)
            if z is None: break
            if np.abs(x - z[0]).max() <= eps and (bz is None or z[1] < bz[1]): bz = (z[0], z[1], mult)
        if bz is not None: row("zfp", eps, bz[2], bz[0], bz[1])
    wr.writerow(dict(dataset=dataset, crop=crop, codec="zstd", param=0, extra="", bpp=zstd_bits(a) / N, maxerr=0, psnr=0))
    f.flush()
f.close(); print("done ->", OUT)
