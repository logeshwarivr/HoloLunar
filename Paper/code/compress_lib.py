import io
import numpy as np, pywt, constriction, zstandard as zstd
from PIL import Image

T, WAV, LVL = 256, "bior4.4", 3

def ans_bits(sym):
    sym = np.asarray(sym).ravel().astype(np.int64)
    vals, counts = np.unique(sym, return_counts=True)
    if len(vals) == 1:
        return 64
    probs = (counts / counts.sum()).astype(np.float64)
    idx = np.searchsorted(vals, sym).astype(np.int32)
    model = constriction.stream.model.Categorical(probs, perfect=False)
    c = constriction.stream.stack.AnsCoder()
    c.encode_reverse(idx, model)
    comp = c.get_compressed()
    assert np.array_equal(constriction.stream.stack.AnsCoder(comp).decode(model, len(idx)), idx)
    return 32 * len(comp) + 48 * len(vals)

def psnr(a, b):
    return float(10 * np.log10(1.0 / (np.mean((a - b) ** 2) + 1e-12)))

def jp2_roundtrip(x, ratio):
    u = np.round(x * 65535).astype(np.uint16); buf = io.BytesIO()
    Image.fromarray(u).save(buf, "JPEG2000", quality_mode="rates", quality_layers=[ratio])
    nbytes = len(buf.getvalue()); buf.seek(0)
    return np.array(Image.open(buf)).astype(np.float32) / 65535, 8 * nbytes

def hybrid_from_base(x, y0, b0, eps):
    q = np.round((x - y0) / (2 * eps)).astype(np.int32)
    return y0 + 2 * eps * q, b0 + ans_bits(q)

def wavelet_codec(x, eps, mults=(1, 2, 4, 8)):
    best = None
    for m in mults:
        h, w = x.shape
        P = np.pad(x, ((0, (-h) % T), (0, (-w) % T)), mode="edge")
        out = np.zeros_like(P); wd = 2 * eps * m; qs, rs = [], []
        for i in range(0, P.shape[0], T):
            for j in range(0, P.shape[1], T):
                t = P[i:i+T, j:j+T]
                arr, sl = pywt.coeffs_to_array(pywt.wavedec2(t, WAV, level=LVL, mode="periodization"))
                q = np.round(arr / wd).astype(np.int32)
                xh = pywt.waverec2(pywt.array_to_coeffs(q * wd, sl, output_format="wavedec2"), WAV, mode="periodization")[:T, :T]
                qr = np.round((t - xh) / (2 * eps)).astype(np.int32)
                out[i:i+T, j:j+T] = xh + qr * (2 * eps)
                qs.append(q.ravel()); rs.append(qr.ravel())
        bits = ans_bits(np.concatenate(qs)) + ans_bits(np.concatenate(rs))
        if best is None or bits < best[1]:
            best = (out[:h, :w], bits, m)
    return best

def zfp_codec(x, tol):
    try:
        import zfpy
    except ImportError:
        return None
    comp = zfpy.compress_numpy(x.astype(np.float32), tolerance=tol)
    return zfpy.decompress_numpy(comp), 8 * len(comp)

def zstd_bits(a):
    return 8 * len(zstd.ZstdCompressor(level=19).compress(np.ascontiguousarray(a, dtype=np.float32).tobytes()))

def slope_deg(z, p):
    gy, gx = np.gradient(z.astype(np.float64), p)
    return np.degrees(np.arctan(np.hypot(gx, gy)))
