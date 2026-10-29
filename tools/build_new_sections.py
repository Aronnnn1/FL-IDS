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
NOVELTY = """
<section id="novelty">
  <h2>What is new in FL-IDS</h2>
  <p>Each part of FL-IDS on its own has published precedent (listed below). What we did not find in the literature is
  all five working together as one system, plus the four contributions of our own listed here. Every claim points to a
  measured result on this site.</p>
  <div class="table-wrap"><table class="ptable novelty">
    <thead><tr><th>#</th><th>Novel element</th><th>Why it matters</th><th>Evidence</th></tr></thead>
    <tbody>
      <tr><td>1</td><td style="white-space:normal"><b>The five-part combination</b>: boosting-first cascade + federated
      autoencoder backstop + trust-filtered aggregation + Flower federated learning + SDN mitigation, as one end-to-end system</td>
      <td style="white-space:normal">Detection, collaboration without sharing raw traffic, poisoning resistance and automatic
      blocking usually appear in separate papers; here a verdict flows from federated training to a real OpenFlow drop rule</td>
      <td style="white-space:normal">Real Phase A &rarr; Phase B run: Backdoor blocked, rule read back from the switch
      (<a href="#verification">Verification</a>, <a href="#journey">Journey</a>)</td></tr>
      <tr><td>2</td><td style="white-space:normal"><b>A poisoning-protected anomaly backstop</b>: the autoencoder is trained
      only on traffic the classifier passes as normal, and its federated updates go through a trust filter that works on
      weight <i>deltas</i> against a coordinate-wise median (cosine sign check + MAD outlier + EMA trust history) before a
      trimmed mean</td>
      <td style="white-space:normal">The backstop is what catches attacks the classifier never saw, and it is exactly the
      part a malicious client would target</td>
      <td style="white-space:normal">30% attackers: autoencoder-alone recall 0.712 with the filter vs. 0.002 with plain
      FedAvg (loss 5&times;10<sup>20</sup>); zero-day 0.930 vs. 0.795 for boosting alone</td></tr>
      <tr><td>3</td><td style="white-space:normal"><b>Two errors found and fixed in Edge-IIoTset</b>: a placeholder
      spelling (&ldquo;0&rdquo; vs &ldquo;0.0&rdquo;) that tracks the label, and column-shifted MITM rows</td>
      <td style="white-space:normal">One column alone separated normal from attack traffic perfectly (AUROC 1.0), so
      results trained on the released CSV are likely inflated; MITM was repaired from the authors' own capture</td>
      <td style="white-space:normal"><a href="#steps">Step 2</a>; PAPER_NOTES &sect;5.3</td></tr>
      <tr><td>4</td><td style="white-space:normal"><b>Leak-free connection features with an ambiguity ceiling and a strict
      split</b>: service port, payload content and flow features that never use IPs or timestamps as inputs, evaluated on
      whole connections held out of training</td>
      <td style="white-space:normal">Shows <i>why</i> per-packet models stall: 2.31% of rows are identical across classes,
      capping macro recall at 0.969 whatever the model; the new features cut that to 0.01%</td>
      <td style="white-space:normal">99.7% accuracy, 0.983 macro F1 on 397k unseen packets (<a href="#improvements">Accuracy</a>)</td></tr>
      <tr><td>5</td><td style="white-space:normal"><b>Training/live feature parity</b>: Phase B derives the same 130
      features from a live capture with the same code used in training</td>
      <td style="white-space:normal">A model is only as good live as its features; mismatches silently break deployment</td>
      <td style="white-space:normal">99.8% of live rows byte-identical to the capture's training rows</td></tr>
    </tbody>
  </table></div>
  <p class="meta"><b>Precedents (not claimed as new):</b> federated autoencoders for IoT anomaly detection (Mothukuri et al.
  2021; DeepFed 2020), cosine-similarity robust aggregation (FLTrust 2021; SignGuard 2022), a LightGBM + autoencoder
  two-stage IDS (Math. Biosci. Eng. 2023), and FL with SDN mitigation (MiTFed 2023). <b>Caveat:</b> &ldquo;not found&rdquo;
  rests on targeted searches, not a systematic review (see <a href="#caveats">Caveats</a>).</p>
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
  <p class="meta"><b>Scope:</b> this 20-client run uses the in-process simulation (the same client, strategy and
  trust-filter code as the real run, in one Python process). A real run with 20 separate client processes exhausted the
  VM's 7.4 GB of RAM (21 Python processes each loading PyTorch and LightGBM) and was stopped after round 1; it needs a
  machine with more memory. The classifier rows rest on few rows for rare classes (Fingerprinting 4, MITM 1). Single seed.
  Source: <code>results/clients20/per_class_stage_report.csv</code>, <code>logs/clients20/</code>.</p>
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
        trs.append(f"<tr class=\"{cls}\"><td>{phase}</td><td>{label}</td><td>{secs(start)}</td><td>{secs(dur)}</td>"
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
.jtable tr.sub td { font-size: 12px; color: var(--text-secondary, #666); padding-top:2px; padding-bottom:2px; }
.jlegend { font-size:12px; color:var(--text-secondary, #666); margin-bottom:10px; }
.jlegend span { display:inline-block; width:12px; height:10px; border-radius:2px; margin:0 4px 0 0; vertical-align:middle; }
.rounds { position:relative; height:34px; border-bottom:1px solid var(--border, #ccc); margin:8px 12px 4px; }
.rounds span { position:absolute; bottom:4px; transform:translateX(-50%); font-size:10px; background:#2a6f97; color:#fff; border-radius:8px; padding:1px 4px; }
.novelty td:first-child { font-weight:700; }
"""


def main() -> None:
    index = DOCS / "index.html"
    html = index.read_text()
    blocks = {"novelty": NOVELTY, "class-split": class_split(), "clients20": clients20()}
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
