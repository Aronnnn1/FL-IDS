"""Build the Novelty, Class split, 20 clients and Journey sections of docs/index.html.

    python tools/build_new_sections.py <results dir>

Reads results/class_split/*.json, results/clients20/per_class_stage_report.csv,
results/extended/per_class_stage_report.csv and results/journey/*.json, and
replaces the text between <!-- GEN:name --> and <!-- /GEN:name --> markers.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
RES = Path(sys.argv[1] if len(sys.argv) > 1 else "results")


def fmt(n: float) -> str:
    return f"{int(n):,}"


def stage_report(path: Path) -> dict:
    rows = list(csv.DictReader(open(path)))
    out = {}
    for r in rows:
        stage = r["stage"]
        out.setdefault(stage, {})["acc"] = float(r["stage_accuracy"])
        out[stage]["macro_f1"] = float(r["stage_macro_f1"])
        out[stage]["fpr"] = float(r["stage_false_positive_rate"])
        out[stage][r["class"]] = r
    return out


# ---------------------------------------------------------------- novelty
# Each novelty point names the closest published work (verified 2026-10-30)
# and says what FL-IDS adds beyond it. References are numbered below.
REFERENCES = [
    ("mothukuri", "V. Mothukuri et al., &ldquo;Federated-Learning-Based Anomaly Detection for IoT Security Attacks,&rdquo; "
     "<i>IEEE Internet of Things Journal</i>, vol. 9, no. 4, pp. 2545&ndash;2554, 2022.", "https://doi.org/10.1109/JIOT.2021.3077803"),
    ("deepfed", "B. Li et al., &ldquo;DeepFed: Federated Deep Learning for Intrusion Detection in Industrial Cyber&ndash;Physical "
     "Systems,&rdquo; <i>IEEE Trans. Industrial Informatics</i>, vol. 17, no. 8, pp. 5615&ndash;5624, 2021.",
     "https://doi.org/10.1109/TII.2020.3023430"),
    ("zhang", "H. Zhang, L. Ge, G. Zhang, J. Fan, D. Li, C. Xu, &ldquo;A two-stage intrusion detection method based on light "
     "gradient boosting machine and autoencoder,&rdquo; <i>Mathematical Biosciences and Engineering</i>, vol. 20, no. 4, "
     "pp. 6966&ndash;6992, 2023.", "https://doi.org/10.3934/mbe.2023301"),
    ("mitfed", "Z. Abou El Houda, A. S. Hafid, L. Khoukhi, &ldquo;MiTFed: A Privacy Preserving Collaborative Network Attack "
     "Mitigation Framework Based on Federated Learning Using SDN and Blockchain,&rdquo; <i>IEEE Trans. Network Science and "
     "Engineering</i>, vol. 10, no. 4, 2023.", "https://doi.org/10.1109/TNSE.2023.3237367"),
    ("hernandez", "J. L. Hernandez-Ramos et al., &ldquo;Intrusion Detection Based on Federated Learning: A Systematic "
     "Review,&rdquo; <i>ACM Computing Surveys</i>, vol. 57, no. 12, 2025.", "https://doi.org/10.1145/3731596"),
    ("fltrust", "X. Cao, M. Fang, J. Liu, N. Z. Gong, &ldquo;FLTrust: Byzantine-robust Federated Learning via Trust "
     "Bootstrapping,&rdquo; <i>NDSS</i>, 2021.", "https://arxiv.org/abs/2012.13995"),
    ("signguard", "J. Xu, S.-L. Huang, L. Song, T. Lan, &ldquo;Byzantine-robust Federated Learning through Collaborative "
     "Malicious Gradient Filtering (SignGuard),&rdquo; <i>IEEE ICDCS</i>, 2022.", "https://arxiv.org/abs/2109.05872"),
    ("yin", "D. Yin, Y. Chen, K. Ramchandran, P. Bartlett, &ldquo;Byzantine-Robust Distributed Learning: Towards Optimal "
     "Statistical Rates,&rdquo; <i>ICML</i>, PMLR 80, pp. 5650&ndash;5659, 2018.", "https://proceedings.mlr.press/v80/yin18a.html"),
    ("foolsgold", "C. Fung, C. J. M. Yoon, I. Beschastnikh, &ldquo;The Limitations of Federated Learning in Sybil "
     "Settings (FoolsGold),&rdquo; <i>RAID</i>, pp. 301&ndash;316, 2020.", "https://www.usenix.org/conference/raid2020/presentation/fung"),
    ("ferrag", "M. A. Ferrag, O. Friha, D. Hamouda, L. Maglaras, H. Janicke, &ldquo;Edge-IIoTset: A New Comprehensive Realistic "
     "Cyber Security Dataset of IoT and IIoT Applications for Centralized and Federated Learning,&rdquo; <i>IEEE Access</i>, "
     "vol. 10, pp. 40281&ndash;40306, 2022.", "https://doi.org/10.1109/ACCESS.2022.3165809"),
    ("galal", "M. M. Galal, &ldquo;Provenance, Not Behaviour: A Serialisation Artifact in Edge-IIoTset and a Leakage-Free "
     "Benchmark for Precision-Agriculture Intrusion Detection,&rdquo; arXiv:2608.15761 (preprint), 16 Aug 2026.",
     "https://arxiv.org/abs/2608.15761"),
    ("engelen", "G. Engelen, V. Rimmer, W. Joosen, &ldquo;Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case "
     "Study,&rdquo; <i>IEEE Security and Privacy Workshops (SPW)</i>, pp. 7&ndash;12, 2021.",
     "https://doi.org/10.1109/SPW53761.2021.00009"),
    ("arp", "D. Arp et al., &ldquo;Dos and Don'ts of Machine Learning in Computer Security,&rdquo; <i>USENIX Security</i>, "
     "2022.", "https://www.usenix.org/conference/usenixsecurity22/presentation/arp"),
    ("sharafaldin", "I. Sharafaldin, A. H. Lashkari, A. A. Ghorbani, &ldquo;Toward Generating a New Intrusion Detection "
     "Dataset and Intrusion Traffic Characterization,&rdquo; <i>ICISSP</i>, pp. 108&ndash;116, 2018.",
     "https://doi.org/10.5220/0006639801080116"),
    ("breck", "E. Breck, N. Polyzotis, S. Roy, S. E. Whang, M. Zinkevich, &ldquo;Data Validation for Machine Learning,&rdquo; "
     "<i>SysML</i>, 2019.", "https://research.google/pubs/data-validation-for-machine-learning/"),
]
REF_NUM = {key: i + 1 for i, (key, _text, _url) in enumerate(REFERENCES)}


def cite(*keys: str) -> str:
    return "[" + ", ".join(f"<a href=\"#ref-{k}\">{REF_NUM[k]}</a>" for k in keys) + "]"


def novelty() -> str:
    rows = [
        ("The five-part combination",
         "Boosting-first cascade + federated autoencoder backstop + trust-filtered aggregation + Flower federated "
         "learning + SDN mitigation, as one end-to-end system.",
         f"Federated IDS models that keep data on devices {cite('mothukuri', 'deepfed')}; a centralised LightGBM + "
         f"autoencoder two-stage IDS {cite('zhang')}; federated learning with SDN mitigation and blockchain "
         f"{cite('mitfed')}; a systematic review of federated IDS work {cite('hernandez')}.",
         "Each covers a subset of the parts. We found none that combines all five, so a verdict from federated "
         "training ends in a real, verified OpenFlow drop rule.",
         "Real Phase A &rarr; Phase B run: Backdoor blocked, rule read back from the switch "
         "(<a href=\"#verification\">Verification</a>, <a href=\"#journey\">Journey</a>)"),
        ("A poisoning-protected anomaly backstop",
         "The autoencoder trains only on traffic the classifier passes as normal; its federated updates are filtered on "
         "weight <i>deltas</i> against a coordinate-wise median (cosine sign check + MAD outlier test + EMA trust history), "
         "then aggregated with a trimmed mean.",
         f"Trust scores from cosine similarity to a server update computed on a clean root dataset {cite('fltrust')}; "
         f"sign statistics of gradients {cite('signguard')}; coordinate-wise median and trimmed mean {cite('yin')}; "
         f"similarity of client contributions over time {cite('foolsgold')}; the cascade itself is centralised "
         f"{cite('zhang')}.",
         "No clean root dataset on the server: the reference is the clients' own median delta, with trust carried "
         "across rounds. And the defence protects the specific stage that catches unseen attacks.",
         "30% attackers: autoencoder-alone recall 0.712 with the filter vs. 0.002 with plain FedAvg "
         "(loss 5&times;10<sup>20</sup>); zero-day 0.930 vs. 0.795 for boosting alone"),
        ("A repaired MITM class in Edge-IIoTset",
         "The released MITM rows have values under the wrong column names; we rebuilt them from the authors' own capture "
         "with tshark (1,214 broken rows &rarr; 1,229 re-extracted).",
         f"The dataset itself {cite('ferrag')}; the &ldquo;0&rdquo; vs &ldquo;0.0&rdquo; placeholder label leak, "
         f"<b>already reported</b> by {cite('galal')} (we found and fixed it independently, later); data problems "
         f"found and fixed by re-extraction in CICIDS2017 {cite('engelen')}.",
         f"{cite('galal')} keeps the MITM rows as released and does not report the column shift; we found no report of "
         "it. <b>The label leak itself is not claimed as new.</b>",
         "<a href=\"#steps\">Step 2</a>; PAPER_NOTES &sect;5.3"),
        ("Leak-free connection features, a strict split and an ambiguity ceiling",
         "Service-port, payload-content and flow features added to each packet without using IPs or timestamps as "
         "inputs; evaluation on whole connections held out of training; a measured upper bound on any per-packet model.",
         f"Flow features from CICFlowMeter {cite('sharafaldin')}; flow-construction errors in such datasets "
         f"{cite('engelen')}; data snooping and spurious correlations as common pitfalls {cite('arp')}; "
         f"{cite('galal')} uses random stratified and leave-one-device-out splits.",
         "We keep Edge-IIoTset's per-packet rows but give each one its connection's behaviour, evaluate with "
         "connections held out, and show why per-packet models stall (2.31% of rows identical across classes caps "
         "macro recall at 0.969; 0.01% after).",
         "99.7% accuracy, 0.983 macro F1 on 397k unseen packets (<a href=\"#improvements\">Accuracy</a>)"),
        ("Measured training/live feature parity",
         "Phase B derives the same 130 features from a live capture with the same code used in training.",
         f"Training&ndash;serving skew as a known cause of silent failures in deployed ML {cite('breck')}.",
         "We measure it in the IDS loop itself: live rows compared field by field with the capture's training rows.",
         "99.8% of live rows byte-identical to the capture's training rows"),
    ]
    trs = "".join(
        f"<tr><td>{i}</td><td><b>{name}</b><br>{what}</td><td>{prior}</td><td>{adds}</td><td>{evidence}</td></tr>"
        for i, (name, what, prior, adds, evidence) in enumerate(rows, 1)
    )
    refs = "".join(
        f"<li id=\"ref-{key}\">{text} <a href=\"{url}\" target=\"_blank\" rel=\"noopener\">link</a></li>"
        for key, text, url in REFERENCES
    )
    return f"""
<section id="novelty">
  <h2>What is new in FL-IDS</h2>
  <p>For each point: what we built, the closest published work, what we add beyond it, and our measured evidence.
  Each part has precedent on its own; the combination, and the four specifics below, are what we did not find.
  Numbers in brackets refer to the references under the table.</p>
  <div class="table-wrap"><table class="ptable novelty">
    <thead><tr><th>#</th><th>Novel element</th><th>Closest prior work</th><th>What FL-IDS adds</th><th>Our evidence</th></tr></thead>
    <tbody>{trs}</tbody>
  </table></div>
  <h3>References</h3>
  <ol class="refs">{refs}</ol>
  <p class="meta"><b>Caveat:</b> &ldquo;we found none&rdquo; rests on targeted searches (last checked 30 October 2026),
  not a systematic review; see <a href="#caveats">Caveats</a>. One finding we made independently, the
  Edge-IIoTset placeholder label leak, had already been published {cite('galal')}, so it is credited there and not
  claimed.</p>
</section>
"""


# ---------------------------------------------------------------- class split
def class_split() -> str:
    ds = json.load(open(RES / "class_split" / "dataset_classes.json"))
    c20 = json.load(open(RES / "class_split" / "clients20_split.json"))
    names = c20["classes"]
    pool = [sum(cl["per_class"][i] for cl in c20["clients"]) for i in range(len(names))]
    by = {r["class"]: r for r in ds["classes"]}
    clean_total = ds["clean_total"]
    rows = []
    tot = dict(raw=0, clean=0, trainval=0, test=0, cal=0, ev=0, pool=0)
    for i, name in enumerate(names):
        r = by[name]
        test = int(r["classifier_test"] or 0)
        trainval = r["clean"] - test
        cal, ev = c20["calibration_train_per_class"][i], c20["calibration_eval_per_class"][i]
        share = 100 * r["clean"] / clean_total
        bar = max(share, 0.15)
        rows.append(
            f"<tr><td>{name}</td><td>{fmt(r['raw'])}</td><td>{fmt(r['clean'])}</td>"
            f"<td style=\"white-space:nowrap\"><span class=\"sharebar\" style=\"width:{bar * 0.9:.2f}px\"></span>{share:.2f}%</td>"
            f"<td>{fmt(trainval)}</td><td>{fmt(test)}</td><td>{fmt(cal)} / {fmt(ev)}</td><td>{fmt(pool[i])}</td></tr>")
        for k, v in dict(raw=r["raw"], clean=r["clean"], trainval=trainval, test=test, cal=cal, ev=ev, pool=pool[i]).items():
            tot[k] += v
    rows.append(f"<tr class=\"total\"><td><b>Total</b></td><td><b>{fmt(ds['raw_total'])}</b></td><td><b>{fmt(tot['clean'])}</b></td>"
                f"<td>100%</td><td><b>{fmt(tot['trainval'])}</b></td><td><b>{fmt(tot['test'])}</b></td>"
                f"<td><b>{fmt(tot['cal'])} / {fmt(tot['ev'])}</b></td><td><b>{fmt(tot['pool'])}</b></td></tr>")

    head = "".join(f"<th title=\"{n}\">{n.replace('_', ' ')}</th>" for n in names)
    crows = []
    for cl in c20["clients"]:
        cells = "".join(f"<td{' class=\"zero\"' if v == 0 else ''}>{fmt(v)}</td>" for v in cl["per_class"])
        warn = " class=\"warnrow\"" if cl["benign_val"] == 0 else ""
        crows.append(f"<tr{warn}><td>{cl['client']}</td>{cells}<td><b>{fmt(sum(cl['per_class']))}</b></td>"
                     f"<td>{fmt(cl['train'])}</td><td>{fmt(cl['benign_val'])}</td><td>{fmt(cl['test'])}</td></tr>")
    no_val = [str(cl["client"]) for cl in c20["clients"] if cl["benign_val"] == 0]
    sizes = [sum(cl["per_class"]) for cl in c20["clients"]]
    return f"""
<section id="class-split">
  <h2>Class split: all {fmt(ds['raw_total'])} rows of the dataset</h2>
  <p>How many rows of each class there are, and where they go. <b>Raw</b> = the authors' CSV. <b>After cleaning</b> =
  after the MITM repair, the new features and removing exact duplicates (the dataset every model here uses).
  <b>Classifier</b> = the final classifier's flow-grouped split (train includes the 8% used for early stopping).
  <b>Federated</b> = the server's 5% calibration set (bootstrap training / held-back scoring) and the 60,000-row pool
  shared out to the clients.</p>
  <div class="table-wrap"><table class="ptable dense classsplit">
    <thead><tr><th>Class</th><th>Raw</th><th>After cleaning</th><th>Share</th><th>Classifier train</th>
    <th>Classifier test</th><th>Fed. calibration (train / held back)</th><th>Fed. client pool</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
  <p class="meta">Normal traffic is {100 * by['Normal']['clean'] / clean_total:.1f}% of all rows; Fingerprinting and MITM
  are under 0.05% each. MITM has no classifier test rows because all its rows are one connection, which a
  connection-held-out split cannot divide. DDoS_ICMP and Normal lose the most rows to de-duplication (identical packets).
  The MITM repair replaces its 1,214 broken rows with 1,229 re-extracted ones, so {fmt(ds['raw_total'] + 15)} rows enter
  cleaning. Source:
  <code>results/class_split/</code>.</p>

  <h3>The 60,000-row pool split across 20 clients</h3>
  <p>Each class is divided among the clients by a Dirichlet(&alpha; = 0.3) draw (seed 42), so every client sees a very
  different mix &mdash; the non-IID setting federated learning has to cope with. Client sizes range from
  {fmt(min(sizes))} to {fmt(max(sizes))} rows. Grey cells = the client has none of that class.
  Highlighted rows ({', '.join(no_val)}) received no Normal rows for their benign validation slice, so they cannot set an
  anomaly threshold and their autoencoder never flags (their classifier still works).</p>
  <div class="table-wrap"><table class="ptable dense clientsplit">
    <thead><tr><th>Client</th>{head}<th>Total</th><th>Train</th><th>Benign val.</th><th>Test</th></tr></thead>
    <tbody>{''.join(crows)}</tbody>
  </table></div>
</section>
"""


# ---------------------------------------------------------------- 20 clients
def real_runs() -> str:
    """Table of real multi-process runs (10 and 20 client processes, three seeds) from results/real_runs/summary.json."""
    path = RES / "real_runs" / "summary.json"
    if not path.exists():
        return ""
    rows = json.load(open(path))
    trs = "".join(
        f"<tr><td>{r['run']}</td><td>{r['total_s']:.0f}</td><td>{r['attack_macro_recall']:.3f}</td>"
        f"<td>{100 * r['benign_fpr']:.2f}%</td><td>{r['boosting_accuracy']:.4f}</td></tr>"
        for r in rows
    )
    return f"""<h3>Real runs: separate client processes, three seeds</h3>
  <p>Not a simulation: one Flower server plus 10 or 20 separate client processes, 20 rounds, no attackers, on a VM with
  24 GB of RAM (the 7.4 GB machine could not hold 21 processes). Seeds 43 and 44 change the data split, the partition
  and the initialisation.</p>
  <div class="table-wrap"><table class="ptable">
    <thead><tr><th>Run</th><th>Phase A, s</th><th>Attack macro-recall</th><th>False alarms</th><th>Classifier accuracy</th></tr></thead>
    <tbody>{trs}</tbody>
  </table></div>
  <p><b>Reading it:</b> 20 real clients detect attacks as well as 10 in two of three seeds; seed 42 dips to 0.978 and we have
  not traced why. False alarms stay between 2.8% and 4.0%. Even with no attackers the trust filter sometimes excludes honest
  clients whose non-IID updates look unusual (more often at 20 clients). Phase B on the 20-client bundle also blocks the
  Backdoor capture (confidence 0.997, drop rule read back from the switch). Source: <code>results/real_runs/</code>,
  <code>runs/clients20_real/</code>, <code>runs/multiseed/</code>.</p>"""


def clients20() -> str:
    s10 = stage_report(RES / "extended" / "per_class_stage_report.csv")
    s20 = stage_report(RES / "clients20" / "per_class_stage_report.csv")
    c20 = json.load(open(RES / "class_split" / "clients20_split.json"))
    no_val = sum(1 for cl in c20["clients"] if cl["benign_val"] == 0)

    def g(s, stage, cls, col):
        return float(s[stage][cls][col])

    def b(s):
        return s.get("boosting_alone") or s.get("boosting")

    def key(s, short):
        return next(k for k in s if k.startswith(short))

    rows = [
        ("Classifier alone: accuracy / macro F1",
         lambda s: f"{s[key(s, 'boost')]['acc']:.4f} / {s[key(s, 'boost')]['macro_f1']:.4f}"),
        ("Autoencoder alone: attack recall",
         lambda s: f"{g(s, key(s, 'auto'), 'attack', 'recall'):.3f}"),
        ("Autoencoder alone: AUROC (attack vs. normal)",
         lambda s: f"{g(s, key(s, 'auto'), 'attack', 'auroc'):.3f}"),
        ("Cascade: attack detection recall",
         lambda s: f"{g(s, key(s, 'casc'), 'attack', 'recall'):.4f}"),
        ("Cascade: accuracy / macro F1 (normal vs. attack)",
         lambda s: f"{s[key(s, 'casc')]['acc']:.4f} / {s[key(s, 'casc')]['macro_f1']:.4f}"),
        ("Cascade: false alarms on normal traffic",
         lambda s: f"{100 * s[key(s, 'casc')]['fpr']:.2f}%"),
    ]
    trs = "".join(f"<tr><td>{label}</td><td>{f(s10)}</td><td>{f(s20)}</td></tr>" for label, f in rows)
    real = real_runs()
    return f"""
<section id="clients20">
  <h2>Scaling to 20 clients</h2>
  <p>The same 130-feature system, 20 rounds, seed 42, with the 60,000-row pool split across <b>20</b> clients instead of
  10 (Dirichlet &alpha; = 0.3). Scored on the clients' held-out test slices (about 9,000 rows), no attackers.</p>
  <div class="table-wrap"><table class="ptable">
    <thead><tr><th>Metric</th><th>10 clients</th><th>20 clients</th></tr></thead>
    <tbody>{trs}
    <tr><td>Clients with no normal rows to set an alarm threshold</td><td>0</td><td>{no_val} of 20</td></tr>
    <tr><td>Autoencoder data sent per round (all clients)</td><td>786,720 bytes</td><td>1,573,440 bytes</td></tr>
    <tr><td>Time per federated round (in-process)</td><td>&asymp; 3 s</td><td>&asymp; 4.3 s</td></tr>
    </tbody>
  </table></div>
  <p><b>Reading it:</b> doubling the clients leaves detection essentially unchanged &mdash; the cascade still catches
  99.6% of attacks &mdash; while each client gets half as much data. The cost shows in the autoencoder: lower recall on
  its own (0.685 vs. 0.728) and slightly more false alarms (3.7% vs. 3.3%), and {no_val} clients get no normal rows at
  all to calibrate on. Communication per round doubles, since every client sends its update.</p>
  <p class="meta"><b>Scope:</b> the table above is the in-process simulation (the same client, strategy and trust-filter
  code as the real run, in one Python process), single seed. The classifier rows rest on few rows for rare classes
  (Fingerprinting 4, MITM 1). Source: <code>results/clients20/per_class_stage_report.csv</code>, <code>logs/clients20/</code>.</p>
  {real}
</section>
"""


# ---------------------------------------------------------------- journey
def journey() -> str:
    jdir = RES / "journey"
    a = json.load(open(jdir / "phase_a_journey.json"))
    b = json.load(open(jdir / "phase_b_journey.json"))
    rounds = json.load(open(jdir / "rounds.json")) if (jdir / "rounds.json").exists() else []
    total = a["elapsed_s"] + b["elapsed_s"]

    def secs(x: float) -> str:
        return f"{x:.1f} s" if x < 90 else f"{x / 60:.1f} min ({x:.0f} s)"

    steps = []
    t = 0.0
    for phase, j in (("Phase A", a), ("Phase B", b)):
        for st in j["stages"]:
            steps.append((phase, st["label"], t + st["start_s"], st["duration_s"], st.get("substages") or []))
        t += j["elapsed_s"]
    bars, trs = [], []
    for phase, label, start, dur, subs in steps:
        left, width = 100 * start / total, max(100 * dur / total, 0.4)
        cls = "a" if phase == "Phase A" else "b"
        bars.append(f"<div class=\"jbar {cls}\" style=\"left:{left:.2f}%;width:{width:.2f}%\" "
                    f"title=\"{label}: {dur:.1f}s\"></div>")
        trs.append(f"<tr class=\"{cls}\"><td>{phase}</td><td>{label}</td><td>{start:.1f} s</td><td>{secs(dur)}</td>"
                   f"<td>{100 * dur / total:.1f}%</td></tr>")
        for sub in subs:
            trs.append(f"<tr class=\"sub\"><td></td><td>&#8627; {sub['label']}</td><td></td><td>{secs(sub['duration_s'])}</td>"
                       f"<td></td></tr>")
    round_html = ""
    if rounds:
        pts = "".join(f"<span title=\"round {r['round']} done at {r['t']:.1f}s\" style=\"left:{100 * r['t'] / a['elapsed_s']:.2f}%\">{r['round']}</span>"
                      for r in rounds)
        round_html = f"""
  <h3>Inside federated training: when each round finished</h3>
  <div class="rounds">{pts}</div>
  <p class="meta">Position = time since Phase A started ({secs(a['elapsed_s'])} in total). Rounds 3, 6, 9&hellip; are slower
  because the server also continues training the classifier on confirmed alerts.</p>"""
    return f"""
<section id="journey">
  <h2>The whole journey, timed</h2>
  <p>One real end-to-end run: raw dataset &rarr; federated training with 10 separate client
  processes &rarr; model bundle &rarr; live replay of a Backdoor attack through Mininet &rarr; verdict &rarr; drop rule on the
  switch. <b>Total: {secs(total)}</b> (Phase A {secs(a['elapsed_s'])}, Phase B {secs(b['elapsed_s'])}).</p>
  <div class="jtrack" aria-label="Timeline of the run">{''.join(bars)}</div>
  <div class="jlegend"><span class="a"></span>Phase A: training &nbsp; <span class="b"></span>Phase B: live detection and blocking</div>
  <div class="table-wrap"><table class="ptable jtable">
    <thead><tr><th>Phase</th><th>Stage</th><th>Starts at</th><th>Takes</th><th>Share</th></tr></thead>
    <tbody>{''.join(trs)}</tbody>
  </table></div>{round_html}
  <h3>Where is a run right now?</h3>
  <p>Every run now tracks itself (<code>fl_ids/utils/journey.py</code>). Phase A and Phase B log a line as each stage starts
  and ends (<code>[phase_a] stage 3/6 started: Federated training (t+16.3s)</code>), report the round during training
  (<code>round 7/20 finished</code>), and keep <code>journey.json</code> in the run folder up to date with the current
  stage, so a running job can be checked at any moment. The live demo times its own steps the same way and they appear
  above as sub-steps.</p>
  <p class="meta">Scope: one run, seed 42, on the 4-core-equivalent VM; the Phase A feature matrix loads from a cache
  (building it from the raw CSV adds about 1.5&ndash;2 minutes). Source: <code>runs/journey/</code>,
  <code>logs/journey/</code>.</p>
</section>
"""


CSS = """
/* generated sections (tools/build_new_sections.py) */
.sharebar { display:inline-block; height:9px; background:var(--accent, #2a6f97); border-radius:2px; margin-right:6px; vertical-align:middle; }
.classsplit td, .clientsplit td { font-variant-numeric: tabular-nums; }
.classsplit tr.total td { border-top: 2px solid var(--border, #ccc); }
.clientsplit th { font-size: 11px; white-space: normal; min-width: 52px; }
.clientsplit td.zero { color: var(--text-secondary, #888); background: var(--surface-2, rgba(127,127,127,.08)); }
.clientsplit tr.warnrow td { background: rgba(214, 140, 0, .14); }
.jtrack { position:relative; height:30px; border-radius:6px; background:var(--surface-2, rgba(127,127,127,.1)); margin:14px 0 6px; overflow:hidden; }
.jbar { position:absolute; top:4px; bottom:4px; border-radius:3px; border-right:2px solid var(--bg, #fff); }
.jbar.a, .jlegend .a, .jtable tr.a td:first-child { background:#2a6f97; }
.jbar.b, .jlegend .b, .jtable tr.b td:first-child { background:#c8553d; }
.jtable tr.a td:first-child, .jtable tr.b td:first-child { color:#fff; font-weight:600; }
.jtable td { white-space: nowrap; }
.jtable td:nth-child(2) { font-family: inherit; white-space: normal; }
.jtable tr.sub td { font-size: 12px; color: var(--text-secondary, #666); padding-top:2px; padding-bottom:2px; }
.jlegend { font-size:12px; color:var(--text-secondary, #666); margin-bottom:10px; }
.jlegend span { display:inline-block; width:12px; height:10px; border-radius:2px; margin:0 4px 0 0; vertical-align:middle; }
.rounds { position:relative; height:34px; border-bottom:1px solid var(--border, #ccc); margin:8px 12px 4px; }
.rounds span { position:absolute; bottom:4px; transform:translateX(-50%); font-size:10px; background:#2a6f97; color:#fff; border-radius:8px; padding:1px 4px; }
.ptable.novelty td { white-space: normal; font-family: inherit; color: inherit; font-size: 12.5px; }
.novelty td:first-child { font-weight:700; }
.novelty td:nth-child(2) { min-width: 220px; }
.novelty td:nth-child(3), .novelty td:nth-child(4) { min-width: 200px; }
.refs { font-size: 12.5px; color: var(--text-secondary); padding-left: 22px; }
.refs li { margin-bottom: 4px; }
.refs li:target { color: var(--text-primary); background: rgba(214, 140, 0, .14); }
"""


def main() -> None:
    index = DOCS / "index.html"
    html = index.read_text()
    blocks = {"novelty": novelty(), "class-split": class_split(), "clients20": clients20()}
    if (RES / "journey" / "phase_b_journey.json").exists():
        blocks["journey"] = journey()
    for name, body in blocks.items():
        pattern = re.compile(rf"<!-- GEN:{name} -->.*?<!-- /GEN:{name} -->", re.S)
        assert pattern.search(html), f"missing marker for {name}"
        html = pattern.sub(lambda _m: f"<!-- GEN:{name} -->{body}<!-- /GEN:{name} -->", html)
    index.write_text(html)
    css = DOCS / "style.css"
    text = css.read_text()
    marker = "/* generated sections (tools/build_new_sections.py) */"
    text = text.split(marker)[0].rstrip() + "\n" + CSS
    css.write_text(text)
    print("built:", ", ".join(blocks))


if __name__ == "__main__":
    main()
