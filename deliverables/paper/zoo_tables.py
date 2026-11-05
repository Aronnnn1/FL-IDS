"""Build the model-selection tables and figure for the paper from result files only.

Reads experiments/zoo/results/*.json (Edge-IIoTset, this paper) and ~/prior_studies/{mp2,mp3,mp4}.json (the project's
earlier stages, public result files of MP-2, MP-3 and MP-4). Writes deliverables/paper/tab_zoo.tex, tab_prior.tex,
tab_zoo_top.tex and figs/fig_zoo.pdf.
"""
import glob
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables/paper"
PRIOR = Path.home() / "prior_studies"
BLUE, ORANGE, GREEN, RED, GREY, PURPLE = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#6B6B6B", "#CC79A7"

NAMES = {
    "lightgbm": ("LightGBM", "boosting"), "xgboost": ("XGBoost", "boosting"), "catboost": ("CatBoost", "boosting"),
    "hist_gradient_boosting": ("HistGradientBoosting", "boosting"), "random_forest": ("Random forest", "bagging trees"),
    "extra_trees": ("Extra trees", "bagging trees"), "decision_tree": ("Decision tree", "single tree"),
    "gaussian_nb": ("Gaussian naive Bayes", "probabilistic"), "logistic_regression": ("Logistic regression", "linear"),
    "linear_svm": ("Linear SVM", "linear"), "knn": ("k-nearest neighbours", "instance"), "svm_rbf_40k": ("RBF SVM (40k train rows)", "kernel"),
    "mlp": ("MLP", "neural"), "cnn1d": ("1D-CNN", "neural"), "gru": ("GRU (150k train rows)", "neural"),
}
FAMCOL = {"boosting": BLUE, "bagging trees": GREEN, "single tree": GREEN, "probabilistic": GREY, "linear": GREY, "instance": ORANGE,
          "kernel": ORANGE, "neural": RED}


def tex(s):
    return s.replace("_", r"\_").replace("%", r"\%")


# ------------------------------------------------------------ Edge-IIoTset zoo
rows = []
for f in sorted(glob.glob(str(ROOT / "experiments/zoo/results/*_s42.json"))):
    r = json.load(open(f))
    if "error" in r:
        print("error in", f, r["error"])
        continue
    rows.append(r)
rows.sort(key=lambda r: -r["macro_f1"])


def size(r):
    if "parameters" in r:
        return f'{r["parameters"]:,} params'
    return "--"


retime = {}
for f in glob.glob(str(ROOT / "experiments/zoo/results_retime/*_s42.json")):
    r = json.load(open(f))
    if "error" not in r:
        retime[r["model"]] = r
for r in rows:
    if r["model"] in retime:
        r["train_seconds"] = retime[r["model"]]["train_seconds"]
        r["inference_us_per_row"] = retime[r["model"]]["inference_us_per_row"]
        r["_retimed"] = True
lines = []
for r in rows:
    nm, fam = NAMES[r["model"]]
    mark = r"$^\ddagger$" if r.get("_retimed") else ""
    lines.append(f'{tex(nm)} & {fam} & {r["accuracy"]:.4f} & {r["macro_f1"]:.4f} & {r["weighted_f1"]:.4f} & {r["benign_fpr"]:.4f} & '
                 f'{r["train_seconds"]:.0f}{mark} & {r["inference_us_per_row"]:.1f}{mark} \\\\')
(OUT / "tab_zoo.tex").write_text("\n".join(lines) + "\n")
print("zoo rows", len(rows))

# scatter: macro F1 vs training time
fig, ax = plt.subplots(figsize=(3.5, 2.6))
plt.rcParams.update({"font.family": "serif", "font.size": 8})
OFF = {"random_forest": (-6, 7, "right"), "xgboost": (4, -9, "left"), "decision_tree": (-4, -10, "right"), "catboost": (4, 5, "left"),
       "lightgbm": (-3, -11, "right"), "hist_gradient_boosting": (3, 6, "left"), "extra_trees": (-5, -10, "right"),
       "knn": (4, 3, "left"), "cnn1d": (4, 3, "left"), "mlp": (-4, -9, "right"), "gru": (4, 2, "left"),
       "logistic_regression": (4, 3, "left"), "linear_svm": (4, -3, "left"), "svm_rbf_40k": (4, -8, "left"), "gaussian_nb": (4, 2, "left")}
SHORT = {"random_forest": "RF", "xgboost": "XGBoost", "decision_tree": "DT", "catboost": "CatBoost", "lightgbm": "LightGBM",
         "hist_gradient_boosting": "HistGB", "extra_trees": "ET", "knn": "kNN", "cnn1d": "1D-CNN", "mlp": "MLP", "gru": "GRU",
         "logistic_regression": "LR", "linear_svm": "lin. SVM", "svm_rbf_40k": "RBF SVM", "gaussian_nb": "NB"}
for r in rows:
    nm, fam = NAMES[r["model"]]
    x = max(r["train_seconds"], 0.5)
    ax.scatter(x, r["macro_f1"], s=22, color=FAMCOL[fam], zorder=3)
    dx, dy, ha = OFF[r["model"]]
    ax.annotate(SHORT[r["model"]], (x, r["macro_f1"]), fontsize=5.5, xytext=(dx, dy), textcoords="offset points", ha=ha)
ax.set_xscale("log")
ax.set_xlabel("training time (s, log scale)")
ax.set_ylabel("macro F1 on held-out connections")
for fam, col in (("boosting", BLUE), ("tree/bagging", GREEN), ("linear/probabilistic", GREY), ("instance/kernel", ORANGE), ("neural", RED)):
    ax.scatter([], [], s=22, color=col, label=fam)
ax.legend(frameon=False, fontsize=6, loc="lower right")
ax.spines[["top", "right"]].set_visible(False)
(OUT / "figs").mkdir(exist_ok=True)
fig.savefig(OUT / "figs/fig_zoo.pdf", bbox_inches="tight")

# ------------------------------------------------------------ earlier stages
def prior_table(path, title):
    d = json.load(open(path))
    ms = sorted(d["multiclass_all_sorted"], key=lambda m: -m["f1_macro"])
    return d["dataset"], ms


out = []
for tag, nm in (("mp2", "MQTTset"), ("mp3", "DataSense")):
    ds, ms = prior_table(PRIOR / f"{tag}.json", nm)
    print(nm, ds["n_train"], ds["n_test"], ds["n_features"])
    out.append(f'\\textit{{{nm}}} & & & \\\\')
    for m in ms:
        name = m["name"].replace(" (Recurrent)", "").replace(" (Vanilla)", "")
        note = r"$^\dagger$" if m.get("n_train_samples", ds["n_train"]) != ds["n_train"] else ""
        out.append(f'\\quad {tex(name)}{note} & {m["accuracy"]:.4f} & {m["f1_macro"]:.4f} & {m["train_time_sec"]:.1f} \\\\')
(OUT / "tab_prior.tex").write_text("\n".join(out) + "\n")

d4 = json.load(open(PRIOR / "mp4.json"))
c = sorted(d4["combined"], key=lambda r: -r["avg_composite"])
out = []
for r in c[:10]:
    out.append(f'{tex(r["name"])} & {r["family"]} & {r["mqttset"]["f1_macro"]:.4f} & {r["datasense"]["f1_macro"]:.4f} & {r["avg_composite"]:.1f} \\\\')
(OUT / "tab_zoo_top.tex").write_text("\n".join(out) + "\n")
fam = {}
for r in c:
    fam.setdefault(r["family"], []).append((r["mqttset"]["f1_macro"] + r["datasense"]["f1_macro"]) / 2)
print({k: (len(v), round(float(np.mean(v)), 3), round(float(np.max(v)), 3)) for k, v in fam.items()})
print("n models mp4", len(c))

base = {}
for f in glob.glob(str(ROOT / "experiments/zoo/results_base91/*_s42.json")):
    r = json.load(open(f))
    if "error" not in r:
        base[r["model"]] = r
full = {r["model"]: r for r in rows}
out = []
for m, r in sorted(base.items(), key=lambda kv: -kv[1]["macro_f1"]):
    if m in full:
        out.append(f'{tex(NAMES[m][0])} & {r["accuracy"]:.4f} & {r["macro_f1"]:.4f} & {full[m]["macro_f1"]:.4f} & {full[m]["macro_f1"] - r["macro_f1"]:+.4f} \\\\')
(OUT / "tab_zoo_base.tex").write_text("\n".join(out) + "\n")
print("base rows", len(out))
