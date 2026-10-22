from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
d = pd.read_csv(RES / "results.csv")
rows = []
for ds, g in d.groupby("dataset"):
    for codec in ["wavelet", "hybrid", "zfp", "sz3"]:
        for eps, h in g[g.codec == codec].groupby("param"):
            rows.append(dict(dataset=ds, codec=codec, eps=eps, bpp_mean=h.bpp.mean(), bpp_std=h.bpp.std(),
                             maxerr_mean=h.maxerr.mean(), violations=int((h.maxerr > eps + 1e-5).sum()), n=len(h)))
    jp = g[g.codec == "jp2"]
    for eps in sorted(d[d.codec == "hybrid"].param.unique()):
        v = [c[c.maxerr <= eps].bpp.min() for _, c in jp.groupby("crop") if (c.maxerr <= eps).any()]
        if v: rows.append(dict(dataset=ds, codec="jp2_oracle", eps=eps, bpp_mean=np.mean(v), bpp_std=np.std(v),
                               maxerr_mean=np.nan, violations=0, n=len(v)))
S = pd.DataFrame(rows).sort_values(["dataset", "eps", "codec"])
S.to_csv(RES / "summary.csv", index=False)
print(S.to_string(index=False))
best = S.loc[S.groupby(["dataset", "eps"]).bpp_mean.idxmin()][["dataset", "eps", "codec", "bpp_mean"]]
best.to_csv(RES / "winners.csv", index=False); print("\nWinner per dataset and eps:\n", best.to_string(index=False))


# ---- paired per-crop comparison: hybrid vs each other codec ----
prow = []
for ds, g in d.groupby("dataset"):
    for eps in sorted(d[d.codec == "hybrid"].param.unique()):
        per = {}
        for crop, c in g.groupby("crop"):
            r = {}
            for cd in ["wavelet", "hybrid", "zfp", "sz3"]:
                v = c[(c.codec == cd) & (c.param == eps)].bpp
                r[cd] = v.iloc[0] if len(v) else np.nan
            j = c[(c.codec == "jp2") & (c.maxerr <= eps)].bpp
            r["jp2_oracle"] = j.min() if len(j) else np.nan
            per[crop] = r
        P = pd.DataFrame(per).T
        for other in ["wavelet", "zfp", "sz3", "jp2_oracle"]:
            ok = P[[other, "hybrid"]].dropna()
            if len(ok) == 0: continue
            sav = 100 * (ok[other] - ok["hybrid"]) / ok[other]
            prow.append(dict(dataset=ds, eps=eps, vs=other, saving_mean_pct=sav.mean(), saving_std_pct=sav.std(),
                             hybrid_wins=int((ok["hybrid"] < ok[other]).sum()), n=len(ok)))
PR = pd.DataFrame(prow); PR.to_csv(RES / "paired.csv", index=False)
print("\nPaired per-crop savings of hybrid (percent fewer bits):\n", PR.round({"eps": 4, "saving_mean_pct": 1, "saving_std_pct": 1}).to_string(index=False))

style = {"wavelet": ("o", "-"), "hybrid": ("s", "-"), "zfp": ("^", ":"), "sz3": ("v", "-."), "jp2_oracle": ("D", "--")}
for ds, g in S.groupby("dataset"):
    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    for codec, h in g.groupby("codec"):
        mk, ls = style[codec]
        ax.errorbar(h.eps, h.bpp_mean, yerr=h.bpp_std.fillna(0), marker=mk, ls=ls, color="black", mfc="white", ms=4, lw=1, capsize=2, label=codec)
    ax.set(xscale="log", yscale="log", xlabel="Max-error bound (fraction of range)", ylabel="Bitrate (bpp)", title=ds)
    ax.grid(alpha=.3); ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(RES / f"fig_rate_error_{ds}.png", dpi=200); plt.close(fig)
print("saved summary.csv, winners.csv, fig_rate_error_*.png")
