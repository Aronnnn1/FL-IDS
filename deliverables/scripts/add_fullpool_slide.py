"""Add the "The Whole Dataset" result slide and correct the data-scale note on slide 13.

Uses deliverables/report/figures/full_pool_runs.png (made by deliverables/scripts/full_figures.py from results/full/). The deck's
original builder input was lost, so the deck is edited in place; this script is the record of that edit.
  ~/tools-venv/bin/python deliverables/scripts/add_fullpool_slide.py
"""
import copy
import io
import re
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "deliverables/presentation/FL-IDS_Review_Presentation.pptx"
PICTURE = ROOT / "deliverables/report/figures/full_pool_runs.png"
TITLE = "Results: The Whole Dataset"
PIC_BOX = (1436068, 1540688, 9319863, 3000000)

prs = Presentation(DECK)
titles = [s.shapes.title.text_frame.text if s.shapes.title is not None else "" for s in prs.slides]
if TITLE in titles:
    raise SystemExit("slide already added")
template = prs.slides[titles.index("Results: Resisting Sabotage")]

text = ("Everything now trains on all 1.99 million usable messages, with each conversation kept on one side of the exam. Known attacks: still 99.6% caught. "
        "False alarms: about 3% for a typical site, up to 16% of all normal packets, because a few very long normal conversations get flagged "
        "(under 1% of conversations). New attacks: 90–94% detected (was 94–95%). All 14 recorded attacks are blocked in the live demo; 12 are named correctly.")
notes = ("This is the run you asked about: the whole federated system on the whole dataset, six real runs with 10 and 20 sites, three seeds. We also made the test stricter: "
         "all packets of one conversation stay together, so a test packet never has a twin in the practice data. Known attacks are caught as before, so nothing was inflated. "
         "False alarms depend on how you count: per packet some runs flag up to 16 percent of normal packets, but that is a handful of very long normal conversations being flagged as a block; "
         "per conversation it is under one percent. New-attack detection and the trust filter are somewhat weaker at this scale and we do not yet know why. "
         "In the live demo all 14 recorded attacks were blocked; two were labelled as the wrong attack type (the MITM recording as Ransomware, the fingerprinting recording as DDoS). "
         "These are the dataset's own recordings, so it is a demonstration, not a held-out test.")

s = prs.slides.add_slide(template.slide_layout)
for ph in list(s.placeholders):
    ph._element.getparent().remove(ph._element)
for sh in template.shapes:
    if sh.shape_type == 13 and sh.name != "Picture 1":
        s.shapes.add_picture(io.BytesIO(PICTURE.read_bytes()), *[Emu(v) for v in PIC_BOX])
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

lst = prs.slides._sldIdLst
new = list(lst)[-1]
lst.remove(new)
titles = [sl.shapes.title.text_frame.text if sl.shapes.title is not None else "" for sl in prs.slides]
lst.insert(titles.index("Results: One Whole Run, Timed") + 1, new)

for sl in prs.slides:
    if sl.has_notes_slide and "The federated part uses a smaller share" in sl.notes_slide.notes_text_frame.text:
        tf = sl.notes_slide.notes_text_frame
        tf.text = re.sub(r"The federated part uses a smaller share[^.]*\.",
                         "The federated part first ran on a 60 thousand row sample; the main results now use the whole pool, about 1.89 million rows, with each conversation kept together.", tf.text, count=1)
prs.save(DECK)
print("slides:", len(prs.slides))
