"""Add the "Pruning, Smarter Attackers, More Seeds" result slide and update the future-work slide.

Data comes from results/pruning/pruning_during_fl.csv, results/pruning/c10_s42/pruning.csv, results/adaptive/adaptive_attack.csv and
results/seeds/summary.json. Run from the repo root in the VM:
  ~/tools-venv/bin/python deliverables/scripts/add_followup_slide.py
(The deck's original builder input was lost, so the deck is edited in place; this script is the record of that edit.)
"""
import copy
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Emu

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "deliverables/presentation/FL-IDS_Review_Presentation.pptx"
TITLE = "Results: Pruning and Smarter Attackers"
PIC_BOX = (2036068, 1540688, 8119863, 3000000)


def rd(p):
    return list(csv.DictReader(open(ROOT / p)))


during = rd("results/pruning/pruning_during_fl.csv")
post = rd("results/pruning/c10_s42/pruning.csv")
adaptive = rd("results/adaptive/adaptive_attack.csv")
seeds = json.load(open(ROOT / "results/seeds/summary.json"))

prs = Presentation(DECK)
if any(s.shapes.title is not None and s.shapes.title.text_frame.text == TITLE for s in prs.slides):
    raise SystemExit("slide already added")
template = next(s for s in prs.slides if s.shapes.title is not None and s.shapes.title.text_frame.text == "Results: Resisting Sabotage")
box = next(sh for sh in template.shapes if sh.name.startswith("Rounded Rectangle"))
try:
    BLUE = "#" + str(box.fill.fore_color.rgb)
except Exception:
    BLUE = "#1F4E79"
ORANGE, GREY = "#E08A1E", "#555555"
plt.rcParams.update({"font.size": 14, "axes.spines.top": False, "axes.spines.right": False})

fig, (a, b) = plt.subplots(1, 2, figsize=(10.8, 4.0))
a.plot([100 * float(r["sparsity"]) for r in during], [float(r["autoencoder_alone_attack_macro_recall"]) for r in during], "o-", color=BLUE, lw=2,
       label="pruned while training")
a.plot([100 * float(r["sparsity"]) for r in post if float(r["sparsity"]) in (0, .5, .7, .8, .9)], [float(r["ae_attack_macro_recall"]) for r in post if float(r["sparsity"]) in (0, .5, .7, .8, .9)],
       "s--", color=ORANGE, lw=2, label="pruned after training")
a.set(xlabel="weights removed (%)", ylabel="new-attack backstop recall", title="Shrinking the model", ylim=(0, 0.85))
a.legend(frameon=False, fontsize=11)
for i, kind in enumerate(("sign_flip", "stealth")):
    rows = [r for r in adaptive if r["attack"] == kind]
    b.bar([j + (i - 0.5) * 0.38 for j in range(3)], [float(r["malicious_client_survival_rate"]) for r in rows], 0.38,
          color=BLUE if kind == "sign_flip" else ORANGE, label="simple attacker" if kind == "sign_flip" else "smarter (stealth) attacker")
b.set_xticks(range(3))
b.set_xticklabels(["20%", "30%", "40%"])
b.set(xlabel="share of sites that are attackers", ylabel="attacker updates let through", title="Fooling the filter", ylim=(0, 1))
b.legend(frameon=False, fontsize=11, loc="upper right")
buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)
buf.seek(0)

z = seeds["zero_day_mean"]["Cascade"]
text = (
    "Removing 70% of the detector's weights costs little if done while training (backstop recall "
    f"{float(during[0]['autoencoder_alone_attack_macro_recall']):.2f} to {float(next(r for r in during if float(r['sparsity']) == .7)['autoencoder_alone_attack_macro_recall']):.2f}), "
    "but ruins it if done afterwards. A smarter attacker slips past the filter most of the time, though known attacks are still caught. "
    f"Across 3 seeds, new-attack detection stays {min(z):.2f}–{max(z):.2f}."
)
notes = (
    "Three follow-ups. First, weight pruning, which was one of our objectives: pruned while the shared model trains, 70 percent of the weights can go and the backstop barely changes; pruned afterwards it collapses. "
    "Second, a smarter attacker that knows how our filter works: it gets through most of the time, which is a real weakness, although the first-stage classifier still catches known attacks. "
    "Third, we repeated the big experiments with two more seeds and the conclusions held. Limits: single seed for pruning and the smart attacker, and we did not test new-attack detection against the smart attacker."
)
s = prs.slides.add_slide(template.slide_layout)
for ph in list(s.placeholders):
    ph._element.getparent().remove(ph._element)
for sh in template.shapes:
    if sh.shape_type == 13 and sh.name != "Picture 1":
        s.shapes.add_picture(buf, *[Emu(v) for v in PIC_BOX])
    elif sh.shape_type == 13:
        s.shapes.add_picture(io.BytesIO(sh.image.blob), sh.left, sh.top, sh.width, sh.height)
    else:
        s.shapes._spTree.append(copy.deepcopy(sh._element))
s.shapes.title.text_frame.paragraphs[0].runs[0].text = TITLE
for extra in s.shapes.title.text_frame.paragraphs[0].runs[1:]:
    extra.text = ""
body = next(sh for sh in s.shapes if sh.name.startswith("Rounded Rectangle"))
paras = body.text_frame.paragraphs
paras[0].runs[0].text = "What it shows"
paras[1].runs[0].text = text
for extra in paras[1].runs[1:]:
    extra.text = ""
s.notes_slide.notes_text_frame.text = notes

# position: right after "Results: One Whole Run, Timed"
lst = prs.slides._sldIdLst
ids = list(lst)
new = ids[-1]
lst.remove(new)
titles = [sl.shapes.title.text_frame.text if sl.shapes.title is not None else "" for sl in prs.slides]
pos = titles.index("Results: One Whole Run, Timed") + 1
lst.insert(pos, new)

# future work slide: weight pruning is now done
for sl in prs.slides:
    if sl.shapes.title is not None and sl.shapes.title.text_frame.text.strip() == "Future Enhancements":
        for sh in sl.shapes:
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    if p.text.startswith("Apply weight pruning"):
                        runs = p.runs
                        runs[0].text = "Send sparse updates and test pruned models on new attacks (pruning itself is done; communication is not yet reduced)"
                        for extra in runs[1:]:
                            extra.text = ""
prs.save(DECK)
print("slides:", len(prs.slides))
