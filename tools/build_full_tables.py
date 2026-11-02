"""Tables for the full-pool results (markdown for PAPER_NOTES, LaTeX for the report, HTML for the results page).

Everything is read from result files: results/full/summary.md (made by tools/summarize_full.py), per-run breakdowns and
connection-level false-alarm files under results/full/<tag>/, the 60k-pool comparison runs (results/real_runs/), and
logs/full/phase_b_all/summary.log. Output: results/full/tables.{json,md,tex,html}.
    python3 tools/build_full_tables.py
"""
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "results/full"
T = {}  # slug -> (caption, header, rows)


def rd(p):
    with open(p) as fh:
        return list(csv.DictReader(fh))


# 1. tables parsed from summarize_full's markdown -----------------------------------------------------------------------
SLUGS = {"Ablation at 30%": "ablation", "Poisoning sweep": "sweep", "Zero-day (leave one attack class out), full pool: mean": "zeroday_mean",
         "Stealth attacker": "stealth", "Pruning during": "pruning", "Per-client z-score clip": "clip"}
md = (FULL / "summary.md").read_text() if (FULL / "summary.md").exists() else ""
zero_tables = 0
for block in re.split(r"\n(?=### )", md):
    if not block.startswith("### "):
        continue
    title, *rest = block.split("\n", 1)
    title = title[4:].strip()
    body = rest[0] if rest else ""
    tables = [t for t in re.split(r"\n\s*\n", body) if t.strip().startswith("|")]
    slug = next((v for k, v in SLUGS.items() if title.startswith(k)), None)
    if title.startswith("Zero-day"):
        for i, tb in enumerate(tables):
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in tb.strip().splitlines()]
            T["zeroday_mean" if i == 0 else "zeroday_class"] = (title + ("" if i == 0 else ": per held-out class"), rows[0], rows[2:])
        continue
    if slug and tables:
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in tables[0].strip().splitlines()]
        T[slug] = (title, rows[0], rows[2:])

# 2. real runs: three metrics families side by side -------------------------------------------------------------------
real_rows, cmp_rows = [], []
for tag in sorted(p.name for p in FULL.glob("c*_s*")):
    bd = FULL / tag / "breakdown"
    ff = FULL / tag / "flow_fpr" / "summary.json"
    log = ROOT / f"logs/full/{tag}/phase_a.log"
    if not (bd / "summary.json").exists():
        continue
    sm = json.load(open(bd / "summary.json"))
    pcl = rd(bd / "per_client.csv")
    sec = re.search(r"Phase A done in ([\d.]+)s", log.read_text()).group(1)
    f = json.load(open(ff)) if ff.exists() else {}
    real_rows.append([tag.replace("c", "").replace("_s", " clients, seed "), f"{float(sec):.0f}", f"{sm['cascade']['attack_macro_recall']:.4f}",
                      f"{sm['cascade']['attack_micro_recall']:.4f}", f"{sm['boosting_only']['attack_micro_recall']:.4f}",
                      f"{sm['cascade']['benign_fpr']:.4f}", f"{f['flow_fpr']:.4f}" if f else "n/a",
                      f"{sum(int(r['test_rows']) for r in pcl):,}", str(sum(r['threshold_infinite'] == 'True' for r in pcl))])
T["real_full"] = ("Real multi-process Phase A on the full pool (1.89M rows), split by connection, 20 rounds, no attackers",
                  ["Run", "Phase A s", "Attack macro-recall", "Attack micro recall", "Classifier-only micro recall", "Packet-level false alarms",
                   "Connection-level false alarms", "Test rows", "Clients with no benign validation rows"], real_rows)

# 3. before / after: 60k row-level vs 60k grouped vs full grouped ----------------------------------------------------
def line(label, summary_path):
    s = json.load(open(summary_path))
    return [label, f"{s['cascade']['attack_macro_recall']:.4f}", f"{s['cascade']['attack_micro_recall']:.4f}",
            f"{s['boosting_only']['attack_micro_recall']:.4f}", f"{s['cascade']['benign_fpr']:.4f}"]


cmp_rows = []
for tag, lab in (("c10_s42", "10 clients, seed 42"), ("c10_s43", "10 clients, seed 43"), ("c10_s44", "10 clients, seed 44"),
                 ("c20_s42", "20 clients, seed 42"), ("c20_s43", "20 clients, seed 43"), ("c20_s44", "20 clients, seed 44")):
    a, b = ROOT / f"results/real_runs/{tag}/summary.json", FULL / tag / "breakdown/summary.json"
    if a.exists() and b.exists():
        cmp_rows.append(line(f"{lab}: 60k pool, split by row", a))
        cmp_rows.append(line(f"{lab}: full pool, split by connection", b))
lk = ROOT / "results/real_runs/leakcheck_c10_s42/summary.json"
if lk.exists():
    cmp_rows.insert(2, line("10 clients, seed 42: 60k pool, split by connection", lk))
T["pool_compare"] = ("The same runs at the earlier scale and now (macro-recall includes only attack types present in the test slices)",
                     ["Setting", "Attack macro-recall", "Attack micro recall", "Classifier-only micro recall", "Benign FPR (packets)"], cmp_rows)

# 4. per-class for the first full run -----------------------------------------------------------------------------------
pc = FULL / "c10_s42/breakdown/per_class_recall.csv"
if pc.exists():
    T["per_class"] = ("Recall per attack type, 10 clients, seed 42, full pool, by stage (held-out test slices)",
                      ["Class", "Test rows", "Classifier alone", "Autoencoder alone", "Cascade"],
                      [[r["class"], r["test_rows"], f"{float(r['boosting_only']):.4f}", f"{float(r['autoencoder_only']):.4f}", f"{float(r['cascade']):.4f}"] for r in rd(pc)])

# 5. Phase B on every capture --------------------------------------------------------------------------------------------
pb = ROOT / "logs/full/phase_b_all/summary.log"
if pb.exists():
    rows = []
    for ln in pb.read_text().splitlines():
        m = re.match(r"(.+?) \| (\w+) \| (\d+)s \| .*?-> ([\w]+) \(confidence ([\d.]+), (\w+) stage, (\d+)/(\d+) packets non-benign\) -> (\w+)", ln)
        if m:
            rows.append([m.group(1).replace("_", " "), m.group(4), m.group(5), m.group(6), f"{int(m.group(7)):,} / {int(m.group(8)):,}", m.group(9), m.group(3) + " s"])
    T["phase_b_all"] = ("Phase B on every attack capture (10 clients, seed 42, full-pool bundle): class chosen, confidence, deciding stage, packets flagged, action",
                        ["Capture", "Classified as", "Confidence", "Stage", "Packets flagged", "Action", "Wall time"], rows)

json.dump({k: {"caption": c, "header": h, "rows": r} for k, (c, h, r) in T.items()}, open(FULL / "tables.json", "w"), indent=1)


def mdt(k):
    c, h, r = T[k]
    return f"**{c}**\n\n| " + " | ".join(h) + " |\n|" + "---|" * len(h) + "\n" + "\n".join("| " + " | ".join(map(str, x)) + " |" for x in r) + "\n"


def tex(k):
    c, h, r = T[k]
    esc = lambda s: str(s).replace("\\", "").replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")  # noqa: E731
    size = "\\scriptsize" if len(h) >= 5 else "\\small"
    return (f"\\begin{{table}}[H]\n\\centering\n{size}\n\\setlength{{\\tabcolsep}}{{3pt}}\n\\renewcommand{{\\arraystretch}}{{1.15}}\n"
            f"\\begin{{tabular}}{{|l|{'c|' * (len(h) - 1)}}}\n\\hline\n" + " & ".join("\\textbf{" + esc(x) + "}" for x in h) + " \\\\ \\hline\n"
            + "\n".join(" & ".join(esc(x) for x in row) + r" \\ \hline" for row in r) + f"\n\\end{{tabular}}\n\\caption{{{esc(c)}}}\n\\label{{tab:full_{k}}}\n\\end{{table}}\n")


def htm(k):
    c, h, r = T[k]
    e = html.escape
    return (f"<p class=\"src\"><b>{e(c)}</b></p>\n<div class=\"table-wrap\"><table class=\"ptable\">\n<thead><tr>" + "".join(f"<th>{e(x)}</th>" for x in h)
            + "</tr></thead>\n<tbody>\n" + "\n".join("<tr>" + "".join(f"<td>{e(str(x))}</td>" for x in row) + "</tr>" for row in r) + "\n</tbody></table></div>\n")


(FULL / "tables.md").write_text("\n".join(mdt(k) for k in T))
(FULL / "tables.tex").write_text("\n".join(tex(k) for k in T))
(FULL / "tables.html").write_text("\n".join(f"<!-- {k} -->\n{htm(k)}" for k in T))
print(sorted(T))
print("\n".join(mdt(k) for k in ("real_full", "pool_compare") if k in T))
