# pip install numpy pywavelets pillow zstandard matplotlib rasterio
import io, lzma, csv
import numpy as np, pywt, zstandard as zstd
import matplotlib.pyplot as plt
import rasterio
from PIL import Image

# ---------------- 1. LOAD DATA ----------------
D = "D:/HoloLunar/Data/"

def read_raw(p):
    return np.nan_to_num(rasterio.open(D + p).read(1).astype(np.float32))

def norm(x):
    return (x - x.min()) / (x.max() - x.min() + 1e-9)

dem_raw = read_raw("dem_faustini_v2.tif")
DEM_SPAN = float(dem_raw.max() - dem_raw.min())        # metres (if DEM is in metres)
dem = norm(dem_raw)
gy, gx = np.gradient(dem)

layers = {
    "ice_prob": norm(read_raw("ice_confidence_faustini_SIMULATED.tif")),
    "DEM": dem,
    "slope": norm(np.hypot(gx, gy)),   # derived from the DEM
}
# scale to convert normalized error -> real units (DEM in metres, others stay normalized)
SCALE = {"ice_prob": 1.0, "DEM": DEM_SPAN, "slope": 1.0}
UNIT = {"ice_prob": "norm", "DEM": "m", "slope": "norm"}

for k, v in layers.items():
    print(k, v.shape, v.dtype)
print(f"DEM range: {DEM_SPAN:.1f} (units of the file, assumed metres)")

H, W = dem.shape
s = min(256, H // 4, W // 4)
ROIS = {
    "A": (int(.1*H), int(.1*H)+s, int(.1*W), int(.1*W)+s),
    "B": (int(.4*H), int(.4*H)+s, int(.4*W), int(.4*W)+s),
    "C": (int(.7*H), int(.7*H)+s, int(.7*W), int(.7*W)+s),
}

# ---------------- 2. METRICS ----------------
def psnr(a, b):
    return 10 * np.log10(1.0 / (np.mean((a - b) ** 2) + 1e-12))

def mean_iou(a, b):
    thr = np.percentile(a, 80)          # "high-value" region threshold
    vals = []
    for r0, r1, c0, c1 in ROIS.values():
        A, B = a[r0:r1, c0:c1] > thr, b[r0:r1, c0:c1] > thr
        vals.append((A & B).sum() / max((A | B).sum(), 1))
    return float(np.mean(vals))

# ---------------- 3. PROPOSED CODEC ----------------
T = 256
WAV, LVL = "bior4.4", 3                 # bior4.4 = CDF 9/7

def proposed(x, eps, mult):
    """Tile -> DWT -> quantize -> residual stage -> LZMA. Guarantees |err| <= eps."""
    Hh, Ww = x.shape
    P = np.pad(x, ((0, (-Hh) % T), (0, (-Ww) % T)), mode="edge")
    out = np.zeros_like(P)
    wd = 2 * eps * mult
    qs, rs = [], []
    for i in range(0, P.shape[0], T):
        for j in range(0, P.shape[1], T):
            t = P[i:i+T, j:j+T]
            c = pywt.wavedec2(t, WAV, level=LVL, mode="periodization")
            arr, sl = pywt.coeffs_to_array(c)
            q = np.round(arr / wd).astype(np.int16)
            xh = pywt.waverec2(
                pywt.array_to_coeffs(q * wd, sl, output_format="wavedec2"),
                WAV, mode="periodization")[:T, :T]
            qr = np.round((t - xh) / (2 * eps)).astype(np.int16)   # residual stage
            out[i:i+T, j:j+T] = xh + qr * (2 * eps)
            qs.append(q.ravel()); rs.append(qr.ravel())
    bits = 8 * (len(lzma.compress(np.concatenate(qs).tobytes())) +
                len(lzma.compress(np.concatenate(rs).tobytes())))
    return out[:Hh, :Ww], bits

def proposed_best(x, eps, mults=(1, 2, 4, 8)):
    best = None
    for m in mults:
        y, b = proposed(x, eps, m)
        if best is None or b < best[1]:
            best = (y, b, m)
    return best

# ---------------- 4. BASELINES (16-bit) ----------------
def to16(x):   return np.round(x * 65535).astype(np.uint16)
def from16(u): return u.astype(np.float32) / 65535

def zstd_lossless(x):
    u = to16(x)
    return from16(u), 8 * len(zstd.ZstdCompressor(level=19).compress(u.tobytes()))

def png_lossless(x):
    u = to16(x); buf = io.BytesIO()
    Image.fromarray(u).save(buf, "PNG", optimize=True)
    return from16(u), 8 * buf.tell()

def jp2(x, ratio):
    u = to16(x); buf = io.BytesIO()
    Image.fromarray(u).save(buf, "JPEG2000", quality_mode="rates", quality_layers=[ratio])
    buf.seek(0)
    y = np.array(Image.open(buf)).astype(np.float32) / 65535
    return y, 8 * len(buf.getvalue())

# ---------------- 5. EXPERIMENT ----------------
EPS = [0.002, 0.005, 0.01, 0.02, 0.05]
JP2_RATIOS = [2, 4, 6, 8, 10, 12, 16, 32, 64, 128, 256]
rows = []   # (layer, method, CR, bpp, PSNR, maxErr_units, IoU, bound)

for name, x in layers.items():
    N, raw, sc = x.size, 16 * x.size, SCALE[name]
    use_iou = name != "DEM"            # DEM IoU is unreliable -> report error in metres instead
    print("Processing", name)
    for eps in EPS:
        y, b, m = proposed_best(x, eps)
        err = float(np.abs(x - y).max())
        assert err <= eps + 1e-5, f"bound violated: {err} > {eps}"
        rows.append((name, f"Proposed e={eps} (m={m})", raw / b, b / N, psnr(x, y),
                     err * sc, mean_iou(x, y) if use_iou else float("nan"), "YES"))
    for r in JP2_RATIOS:
        y, b = jp2(x, r)
        rows.append((name, f"JP2 {r}:1", raw / b, b / N, psnr(x, y),
                     float(np.abs(x - y).max()) * sc,
                     mean_iou(x, y) if use_iou else float("nan"), "no guarantee"))
    for nm, f in [("zstd", zstd_lossless), ("PNG", png_lossless)]:
        y, b = f(x)
        rows.append((name, nm, raw / b, b / N, psnr(x, y), 0.0,
                     1.0 if use_iou else float("nan"), "lossless"))

# ---------------- 6. TABLE + CSV ----------------
def f_iou(v): return "   n/a" if np.isnan(v) else f"{v:6.3f}"

hdr = ("layer", "method", "CR", "bpp", "PSNR", "maxErr", "IoU", "bound")
print(f"\n{hdr[0]:9}{hdr[1]:24}{hdr[2]:>8}{hdr[3]:>8}{hdr[4]:>8}{hdr[5]:>10}{hdr[6]:>7}  {hdr[7]}")
for r in rows:
    print(f"{r[0]:9}{r[1]:24}{r[2]:8.2f}{r[3]:8.3f}{r[4]:8.2f}{r[5]:10.4f} {f_iou(r[6])}  {r[7]}")
print("\nmaxErr units: ice_prob and slope = normalized [0,1]; DEM = metres")

with open("results.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(rows)

# ---------------- 7. PLOTS (one figure per layer) ----------------
for name in layers:
    use_iou = name != "DEM"
    ncols = 3 if use_iou else 2
    fig, ax = plt.subplots(1, ncols, figsize=(5 * ncols, 4))
    for pre, lab in [("Proposed", "Proposed (error-bounded)"), ("JP2", "JPEG2000")]:
        d = sorted([r for r in rows if r[0] == name and r[1].startswith(pre)], key=lambda r: r[3])
        ax[0].plot([r[3] for r in d], [r[4] for r in d], "o-", label=lab)
        ax[1].plot([r[3] for r in d], [r[5] for r in d], "o-", label=lab)
        if use_iou:
            ax[2].plot([r[3] for r in d], [r[6] for r in d], "o-", label=lab)
    ax[0].set(xlabel="bitrate (bpp)", ylabel="PSNR (dB)", title=f"{name}: rate vs PSNR")
    ax[1].set(xlabel="bitrate (bpp)", ylabel=f"Max abs error ({UNIT[name]})",
              title=f"{name}: rate vs max error", yscale="log")
    if use_iou:
        ax[2].set(xlabel="bitrate (bpp)", ylabel="High-value region IoU",
                  title=f"{name}: rate vs IoU")
    for a in ax: a.legend(); a.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(f"rd_{name}.png", dpi=200); plt.close()

print("Saved: results.csv, rd_ice_prob.png, rd_DEM.png, rd_slope.png")