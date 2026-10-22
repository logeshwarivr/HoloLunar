import json
from pathlib import Path
import numpy as np, pandas as pd, streamlit as st
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from compress_lib import *

ROOT = Path(__file__).resolve().parent.parent
CROPS, RES = ROOT / "data" / "crops", ROOT / "results"
EPS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]
RATIOS = [2, 4, 8, 16, 32, 64, 128, 256, 512]
NAMES = {"hybrid": "Hybrid: JPEG2000 + residual (guaranteed)", "wavelet": "Wavelet + residual (guaranteed)",
         "zfp": "ZFP (error-bounded, tolerance)", "jp2": "JPEG2000 only (no guarantee)"}

st.set_page_config(page_title="Error-Bounded Compression Demo", layout="wide")
meta = json.load(open(CROPS / "meta.json")) if (CROPS / "meta.json").exists() else {}
files = sorted(p.stem for p in CROPS.glob("*.npy"))
if not files:
    st.error(f"No crops found in {CROPS}. Run make_crops.py first."); st.stop()

@st.cache_data
def load(crop):
    a = np.load(CROPS / f"{crop}.npy").astype(np.float32)
    return a, float(a.min()), float(a.max())

@st.cache_data(show_spinner="Compressing...")
def run(crop, codec, eps, ratio):
    a, lo, hi = load(crop); x = ((a - lo) / (hi - lo)).astype(np.float32)
    if codec == "hybrid":
        best = None
        for r in RATIOS[2:]:
            y0, b0 = jp2_roundtrip(x, r); y, b = hybrid_from_base(x, y0, b0, eps)
            if best is None or b < best[1]: best = (y, b, f"JPEG2000 base {r}:1 + residual step 2\u03B5")
        return best
    if codec == "wavelet":
        y, b, m = wavelet_codec(x, eps); return y, b, f"coefficient step multiplier m = {m}"
    if codec == "zfp":
        z = zfp_codec(x, eps)
        return None if z is None else (z[0], z[1], "ZFP fixed-accuracy mode")
    y, b = jp2_roundtrip(x, ratio); return y, b, f"JPEG2000 {ratio}:1"

@st.cache_data(show_spinner="Matching JPEG2000 bitrate...")
def jp2_matched(crop, bits):
    a, lo, hi = load(crop); x = ((a - lo) / (hi - lo)).astype(np.float32)
    outs = {r: jp2_roundtrip(x, r) for r in RATIOS}
    r = min(RATIOS, key=lambda r: abs(outs[r][1] - bits))
    return outs[r][0], outs[r][1], f"JPEG2000 {r}:1"

# ---------------- sidebar ----------------
st.sidebar.title("Controls")
crop = st.sidebar.selectbox("Raster crop", files)
ds = crop.rsplit("_", 1)[0]; info = meta.get(ds, {}); kind = info.get("kind", "dem"); pix = info.get("pixel_m", 1.0)
unit = "m" if kind == "dem" else "DN"
eps = st.sidebar.select_slider("Max-error bound \u03B5 (fraction of range)", options=EPS, value=0.01)
codec = st.sidebar.radio("Codec", list(NAMES), format_func=lambda k: NAMES[k])
ratio = st.sidebar.select_slider("JPEG2000 ratio", options=RATIOS, value=32) if codec == "jp2" else 32
compare = st.sidebar.checkbox("Compare with JPEG2000 at the same bitrate", value=True)

a, lo, hi = load(crop); span = hi - lo; x = ((a - lo) / span).astype(np.float32)
res = run(crop, codec, eps, ratio)
st.title("Error-Bounded Compression of Scientific Rasters")
st.caption(f"{crop}  |  {a.shape[0]} \u00D7 {a.shape[1]}  |  value range {span:.2f} {unit}  |  bound \u03B5 = {eps * span:.3f} {unit}")
if res is None:
    st.warning("ZFP is not installed (pip install zfpy). Pick another codec."); st.stop()
y, bits, detail = res
bpp = bits / x.size; merr = float(np.abs(x - y).max())
guaranteed = codec in ("hybrid", "wavelet")

t1, t2, t3 = st.tabs(["Live compression", "Rate vs error (all results)", "Downstream: slope test"])

with t1:
    c = st.columns(4)
    c[0].metric("Bitrate", f"{bpp:.3f} bpp"); c[1].metric("Compression ratio", f"{32 / bpp:.1f}\u00D7", help="vs 32-bit float")
    c[2].metric("Max error", f"{merr * span:.3f} {unit}"); c[3].metric("PSNR", f"{psnr(x, y):.1f} dB")
    if merr <= eps + 1e-6:
        st.success(f"Max error {merr * span:.3f} {unit} is within the bound {eps * span:.3f} {unit}." + (" This is guaranteed by construction." if guaranteed else " Measured only; this codec gives no guarantee."))
    else:
        st.error(f"Bound VIOLATED: max error is {merr / eps:.1f}\u00D7 \u03B5. This codec gives no guarantee.")
    st.caption(detail)

    f, ax = plt.subplots(1, 3, figsize=(13, 4))
    for a_, im, t in [(ax[0], a, "Original"), (ax[1], y * span + lo, "Decoded")]:
        h = a_.imshow(im, cmap="gray", vmin=lo, vmax=hi); a_.set_title(t)
    h = ax[2].imshow(np.abs(x - y) * span, cmap="gray", vmin=0, vmax=eps * span); ax[2].set_title(f"|Error| ({unit}), scale 0 to \u03B5")
    plt.colorbar(h, ax=ax[2], fraction=.046)
    for a_ in ax: a_.axis("off")
    st.pyplot(f); plt.close(f)

    st.subheader("Error distribution")
    entries = [(NAMES[codec], y, bpp)]
    if compare and codec != "jp2":
        yj, bj, dj = jp2_matched(crop, bits); entries.append((f"{dj} (same bitrate)", yj, bj / x.size))
    cols = st.columns(len(entries))
    for col, (nm, yy, bb) in zip(cols, entries):
        e = (x - yy) * span; f, a_ = plt.subplots(figsize=(6, 3))
        a_.hist(e.ravel(), bins=120, color="gray", log=True)
        for s_ in (-1, 1): a_.axvline(s_ * eps * span, color="black", ls="--", lw=1.2)
        a_.set(xlabel=f"Error ({unit})", ylabel="Pixels (log)", title=f"{nm}  |  {bb:.3f} bpp  |  max {np.abs(e).max():.3f} {unit}")
        col.pyplot(f); plt.close(f)
    st.caption("Dashed lines mark \u00B1\u03B5. Every pixel of a guaranteed codec lies between them.")

with t2:
    sp = RES / "summary.csv"
    if not sp.exists(): st.info("Run analyze.py to create results\\summary.csv.")
    else:
        S = pd.read_csv(sp); g = S[S.dataset == ds]
        f, a_ = plt.subplots(figsize=(7, 4.5))
        sty = {"wavelet": ("o", "-"), "hybrid": ("s", "-"), "zfp": ("^", ":"), "jp2_oracle": ("D", "--")}
        for cd, h in g.groupby("codec"):
            mk, ls = sty[cd]; a_.errorbar(h.eps, h.bpp_mean, yerr=h.bpp_std.fillna(0), marker=mk, ls=ls, color="black", mfc="white", ms=5, capsize=2, label=cd)
        a_.plot([eps], [bpp], "*", color="black", ms=16, label="current setting")
        a_.set(xscale="log", yscale="log", xlabel="Max-error bound (fraction of range)", ylabel="Bitrate (bpp), mean over crops", title=f"Dataset: {ds}")
        a_.grid(alpha=.3); a_.legend(fontsize=8); st.pyplot(f); plt.close(f)
        st.dataframe(g[["codec", "eps", "bpp_mean", "bpp_std", "violations", "n"]].round(4))
        st.caption("jp2_oracle = cheapest JPEG2000 setting whose measured error happened to be within the bound (needs hindsight). n = crops where that was possible.")

with t3:
    if kind != "dem": st.info("The slope test applies to elevation (DEM) crops only.")
    else:
        thr = st.slider("Slope class threshold (degrees)", 5, 30, 10)
        s0 = slope_deg(a, pix)[1:-1, 1:-1]; s1 = slope_deg(y * span + lo, pix)[1:-1, 1:-1]; e = np.abs(s1 - s0)
        bound = float(np.degrees(np.sqrt(2) * eps * span / pix))
        c = st.columns(3)
        c[0].metric("Max slope error", f"{e.max():.3f}\u00B0"); c[1].metric("Theoretical bound", f"{bound:.3f}\u00B0", help="degrees(\u221A2 \u00B7 \u03B5 / pixel size)")
        c[2].metric(f"Pixels changing class at {thr}\u00B0", f"{100 * ((s0 > thr) != (s1 > thr)).mean():.2f}%")
        (st.success if e.max() <= bound + 1e-6 else st.warning)(
            "Slope error is within the bound derived from the elevation bound." if e.max() <= bound + 1e-6 else "Slope error exceeds the bound: expected for codecs without an elevation guarantee.")
        f, ax = plt.subplots(1, 3, figsize=(13, 4))
        for a_, im, t in [(ax[0], s0, "Slope, original (deg)"), (ax[1], s1, "Slope, decoded (deg)"), (ax[2], e, "|Slope error| (deg)")]:
            h = a_.imshow(im, cmap="gray"); a_.set_title(t); a_.axis("off"); plt.colorbar(h, ax=a_, fraction=.046)
        st.pyplot(f); plt.close(f)
