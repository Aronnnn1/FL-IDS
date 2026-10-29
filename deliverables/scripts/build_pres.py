"""Presentation version of the FL-IDS deck: BMSCE PP2 template restructured to 24 slides, plain language, speaker notes.

Usage: python build_deck.py <structured.pptx> <out.pptx> <figures dir>
"""

import copy
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.shapes import PP_PLACEHOLDER as PH
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt
from PIL import Image

SRC, OUT, FIG = sys.argv[1], sys.argv[2], Path(sys.argv[3])
DATE = "16-10-2026"
FOOTER = "FL-IDS                         Department of CSE, BMSCE"
TITLE = "FL-IDS: Federated Learning-Based Intrusion Detection System for IoT/IIoT"

NAVY = RGBColor(0x1E, 0x27, 0x61)
TEAL = RGBColor(0x0A, 0x93, 0x96)
CORAL = RGBColor(0xD6, 0x45, 0x50)
INK = RGBColor(0x1B, 0x1B, 0x1B)
MUTED = RGBColor(0x5B, 0x67, 0x70)
TINT = {"navy": RGBColor(0xE3, 0xE7, 0xF4), "teal": RGBColor(0xDD, 0xF1, 0xF2),
        "coral": RGBColor(0xF9, 0xE1, 0xE3), "grey": RGBColor(0xF1, 0xF2, 0xF4)}

# content area of the template's "Title and Content" layout
CX, CY, CW, CH = 838200, 1690688, 10515600, 4486275
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

prs = Presentation(SRC)
S = prs.slides


def ph(slide, kind):
    for s in slide.placeholders:
        t = s.placeholder_format.type
        if kind == "title" and t in (PH.TITLE, PH.CENTER_TITLE):
            return s
        if kind == "body" and s.placeholder_format.idx == 1:
            return s
        if kind == "date" and t == PH.DATE:
            return s
        if kind == "footer" and t == PH.FOOTER:
            return s
    return None


def fix_chrome(slide):
    """Fixed date, corrected footer (BSMCE -> BMSCE), on every slide."""
    d = ph(slide, "date")
    if d is not None:
        p = d.text_frame.paragraphs[0]._p
        for child in list(p):
            if child.tag != A + "pPr":
                p.remove(child)
        r = etree.SubElement(p, A + "r")
        etree.SubElement(r, A + "rPr", lang="en-IN")
        etree.SubElement(r, A + "t").text = DATE
    f = ph(slide, "footer")
    if f is not None:
        runs = f.text_frame.paragraphs[0].runs
        runs[0].text = FOOTER
        for r in runs[1:]:
            r.text = ""


def set_title(slide, text):
    t = ph(slide, "title")
    runs = t.text_frame.paragraphs[0].runs
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def bullets(slide, items, size=20, box=None, space=6):
    """items: str or (str, level) or [(text, bold), ...] runs."""
    b = ph(slide, "body")
    if box:
        b.left, b.top, b.width, b.height = (Emu(v) for v in box)
    tf = b.text_frame
    tf.word_wrap = True
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    first = True
    for it in items:
        lvl = 0
        if isinstance(it, tuple) and isinstance(it[1], int):
            it, lvl = it
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        for r in list(p.runs):
            r._r.getparent().remove(r._r)
        p.level = lvl
        p.space_after = Pt(space)
        runs = it if isinstance(it, list) else [(it, False)]
        for text, bold in runs:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size - 2 * lvl)
            r.font.bold = bold
    return b


def remove_body(slide):
    b = ph(slide, "body")
    if b is not None:
        b._element.getparent().remove(b._element)


def picture(slide, path, x, y, w, h):
    """Fit an image inside (x, y, w, h), centred, aspect kept."""
    iw, ih = Image.open(path).size
    s = min(w / iw, h / ih)
    pw, phh = int(iw * s), int(ih * s)
    return slide.shapes.add_picture(str(path), x + (w - pw) // 2, y + (h - phh) // 2, pw, phh)


def textbox(slide, x, y, w, h, paras, size=16, align=PP_ALIGN.LEFT, color=INK, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = para if isinstance(para, list) else [(para, False)]
        for text, bold in runs:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
    return tb


def card(slide, x, y, w, h, head, lines, tint="navy", accent=NAVY, size=15, head_size=18):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.adjustments[0] = 0.06
    shp.fill.solid()
    shp.fill.fore_color.rgb = TINT[tint]
    shp.line.fill.background()
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Emu(150000))
    tf.margin_top = Emu(120000)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = head
    r.font.size = Pt(head_size)
    r.font.bold = True
    r.font.color.rgb = accent
    for line in lines:
        p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(5)
        runs = line if isinstance(line, list) else [(line, False)]
        for text, bold in runs:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = INK
    return shp


def stat(slide, x, y, w, value, label, color=NAVY):
    textbox(slide, x, y, w, 700000, [[(value, True)]], size=40, color=color)
    textbox(slide, x, y + 720000, w, 600000, [label], size=14, color=MUTED)


def table(slide, x, y, w, rows, col_w, size=14, row_h=330000, bold_last=False, left_all=False):
    t = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, row_h * len(rows)).table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Emu(cw)
    for i, row in enumerate(rows):
        t.rows[i].height = Emu(row_h)
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.text = str(val)
            c.margin_top = c.margin_bottom = Emu(30000)
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if (j == 0 or left_all) else PP_ALIGN.CENTER
            r = p.runs[0]
            r.font.size = Pt(size)
            r.font.bold = i == 0 or (bold_last and i == len(rows) - 1)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if i == 0 else INK
            c.fill.solid()
            c.fill.fore_color.rgb = NAVY if i == 0 else (TINT["teal"] if bold_last and i == len(rows) - 1
                                                         else (TINT["grey"] if i % 2 == 0 else RGBColor(0xFF, 0xFF, 0xFF)))
    return t




GOLD = RGBColor(0xC9, 0x8A, 0x0B)
TINT["gold"] = RGBColor(0xFB, 0xF0, 0xD9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def chip(slide, x, y, w, h, num, head, body, tint="navy", accent=NAVY, size=13, head_size=15):
    """Rounded card with a numbered circle; used for steps and flows."""
    shp = card(slide, x, y, w, h, " ", [body] if body else [], tint=tint, accent=accent,
               size=size, head_size=head_size)
    d = 380000
    textbox(slide, x + 110000 + d + 90000, y + 70000, w - (110000 + d + 90000) - 100000, 450000,
            [[(head, True)]], size=head_size, color=accent, anchor=MSO_ANCHOR.MIDDLE)
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, x + 110000, y + 95000, d, d)
    c.fill.solid()
    c.fill.fore_color.rgb = accent
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(num)
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = WHITE
    return shp


def arrow(slide, x1, y1, x2, y2, color=MUTED):
    conn = slide.shapes.add_connector(1, x1, y1, x2, y2)  # straight
    conn.line.color.rgb = color
    conn.line.width = Pt(2)
    ln = conn.line._get_or_add_ln()
    tail = etree.SubElement(ln, A + "tailEnd")
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    return conn


def label(slide, x, y, w, text, color=MUTED, size=12, align=PP_ALIGN.CENTER, bold=False):
    return textbox(slide, x, y, w, 300000, [[(text, bold)]], size=size, align=align, color=color)


PF = FIG.parent / "out_pres"   # presentation-size charts

for sl in S:
    fix_chrome(sl)

# =============================================================== 1 Title
s = S[0]
t = ph(s, "title")
t.top, t.height = Emu(700000), Emu(1900000)
t.left, t.width = Emu(1100000), Emu(9700000)
p = t.text_frame.paragraphs[0]
for child in list(p._p):
    if child.tag in (A + "r", A + "br"):
        p._p.remove(child)
r = p.add_run()
r.text = TITLE
r.font.size = Pt(38)
team = [("Aaron B Ajay", "1BM23CS003"), ("Aaryan Prakash", "1BM23CS006"),
        ("Amal Roy", "1BM23CS025"), ("Amogh Krishna JS", "1BM23CS029")]
colw = 2500000
x0 = (12192000 - 4 * colw) // 2
for i, (n, u) in enumerate(team):
    textbox(s, x0 + i * colw, 2750000, colw, 650000, [n, u], size=18, align=PP_ALIGN.CENTER)
sub = ph(s, "body")
sub.left, sub.top, sub.width, sub.height = Emu(1524000), Emu(3500000), Emu(9144000), Emu(1655762)
vals = [None, "Mr. Syed Akram", "Assistant Professor", "Department of Computer Science and Engineering",
        "B.M.S. College of Engineering"]
for pp, v in zip(sub.text_frame.paragraphs, vals):
    if v is not None and pp.runs:
        pp.runs[0].text = v
        for rr in pp.runs[1:]:
            rr.text = ""
notes(s, "Good morning. We are presenting FL-IDS: an intrusion detection system for IoT and industrial IoT "
         "networks that learns across many sites without collecting their traffic, resists poisoned training, "
         "catches attacks it has never seen, and blocks attackers on the network switch.")

# =============================================================== 2 Outline (template list kept)
notes(S[1], "This is the flow of the talk: the problem, the design, how we implemented it, the results, and what comes next.")

# =============================================================== 3 SDGs
s = S[2]
remove_body(s)
ph(s, "title").text_frame.paragraphs[0].runs[0].font.size = Pt(36)
cw = (CW - 2 * 250000) // 3
sdgs = [("SDG 9: Industry, Innovation and Infrastructure", ["Enhances secure network infrastructure", "Supports smart systems"], "navy", NAVY),
        ("SDG 11: Sustainable Cities and Communities", ["Secure IoT systems for smart cities, including traffic systems, healthcare and energy grids",
                                                        "Helps ensure safe and reliable operation of connected urban infrastructure"], "teal", TEAL),
        ("SDG 16: Peace, Justice and Strong Institutions", ["Strengthens cybersecurity", "Protects sensitive digital data"], "coral", CORAL)]
for i, (h, lines, tn, ac) in enumerate(sdgs):
    card(s, CX + i * (cw + 250000), CY + 50000, cw, 3250000, h, [("\u2022 " + l) for l in lines],
         tint=tn, accent=ac, size=17, head_size=18)
textbox(s, CX, CY + 3500000, CW, 500000, [[("Promotes ", False), ("secure and resilient digital ecosystems", True)]],
        size=20, align=PP_ALIGN.CENTER)
notes(s, "Three Sustainable Development Goals. SDG 9: we make network infrastructure more secure and support smart "
         "systems. SDG 11: smart cities run on IoT, in traffic systems, healthcare and energy grids, and securing it keeps "
         "that urban infrastructure safe and reliable. SDG 16: the project strengthens cybersecurity and protects "
         "sensitive data. Together, these promote secure and resilient digital ecosystems.")

# =============================================================== 4 Collaboration
s = S[3]
remove_body(s)
card(s, CX, CY + 100000, CW, 1300000, "Category: Not a multidisciplinary project",
     ["A Computer Science and Engineering project; not community-oriented or multidisciplinary."],
     tint="navy", accent=NAVY, size=17, head_size=20)
card(s, CX, CY + 1650000, CW, 1700000, "Field work / collaboration",
     ["No external collaboration.",
      "We use the public Edge-IIoTset dataset and its real packet captures, recorded on a seven-layer "
      "IoT/IIoT testbed with 10+ kinds of sensors (Ferrag et al., IEEE Access, 2022)."],
     tint="grey", accent=MUTED, size=17, head_size=20)
notes(s, "This is not a multidisciplinary or community-oriented project; it sits within computer science and "
         "engineering. We had no external collaborator; all experiments use a public dataset recorded on a real IoT testbed.")

# =============================================================== 5 Problem statement
s = S[4]
remove_body(s)
textbox(s, CX, CY - 80000, CW, 500000,
        ["IoT and industrial IoT devices are everywhere, lightly protected, and attacked constantly."], size=18)
probs = [("Privacy", "Sending every site's raw traffic to one place exposes how a factory or building runs.", "navy", NAVY),
         ("New attacks", "A normal classifier can only name attacks it was trained on.", "teal", TEAL),
         ("Sabotage", "In shared training, a few bad participants can poison the model.", "coral", CORAL),
         ("No action", "Detecting an attack does not stop it.", "gold", GOLD)]
cw = (CW - 3 * 220000) // 4
for i, (h, b, tn, ac) in enumerate(probs):
    card(s, CX + i * (cw + 220000), CY + 550000, cw, 2100000, h, [b], tint=tn, accent=ac, size=15, head_size=19)
card(s, CX, CY + 2850000, CW, 1050000, "Our goal",
     ["One system that solves all four, and classifies attacks with at least 95% accuracy and 0.95 macro F1."],
     tint="grey", accent=NAVY, size=17, head_size=18)
notes(s, "Four problems with existing intrusion detection for IoT. Privacy: central collection of raw traffic. "
         "New attacks: classifiers only know their training labels. Sabotage: shared training can be poisoned. "
         "No action: a detector that only raises alerts doesn't stop anything. Our goal was one system for all "
         "four, with at least 95% accuracy and 0.95 macro F1. Macro F1 means every attack type counts equally, "
         "so a model can't hide poor results on rare attacks behind the large amount of normal traffic.")

# =============================================================== 6 Objectives
s = S[5]
set_title(s, "Objectives")
remove_body(s)
objs = [("Malicious Client Detection & Filtering",
         [("To develop a ", False), ("malicious client detection mechanism", True),
          (" using anomaly-based or trust-based evaluation to identify and filter compromised participants in the federated network.", False)]),
        ("Efficient Privacy-Aware FL Design",
         [("To design a ", False), ("lightweight and efficient federated learning framework", True),
          (" that balances privacy and performance while minimizing computational and communication overhead in resource-constrained IoT environments.", False)]),
        ("Model Optimization for Scalability",
         [("To enhance system scalability by applying ", False), ("model optimization techniques such as weight pruning", True),
          (", reducing computational and communication overhead.", False)]),
        ("Semi-Supervised & Anomaly-Based Detection",
         [("To integrate ", False), ("semi-supervised learning and Autoencoder-based anomaly detection", True),
          (" to effectively identify abnormal or potentially poisoned patterns without relying entirely on labeled data.", False)])]
cw = (CW - 250000) // 2
for i, (h, body) in enumerate(objs):
    x = CX + (i % 2) * (cw + 250000)
    y = CY + (i // 2) * 2150000
    card(s, x, y, cw, 1950000, f"{i + 1}. {h}", [body], tint=["navy", "teal", "coral", "gold"][i],
         accent=[NAVY, TEAL, CORAL, GOLD][i], size=16, head_size=18)
notes(s, "Our four objectives. One: detect and filter malicious clients in federated training, using trust-based "
         "evaluation. Two: a lightweight, privacy-aware federated learning design that keeps computation and "
         "communication low on IoT hardware. Three: model optimization such as weight pruning for scalability; our "
         "model is already small, and pruning itself is future work. Four: autoencoder-based anomaly detection that does "
         "not depend only on labelled data, so it can flag new or poisoned patterns.")

# =============================================================== 7 High level design
s = S[6]
remove_body(s)
steps = [("IoT sites", "10 sites; traffic stays local", "grey", MUTED),
         ("Local learning", "each site trains its own copy", "teal", TEAL),
         ("Server", "checks every update, drops bad ones, combines the rest", "gold", GOLD),
         ("Detector", "trained classifier + anomaly detector", "navy", NAVY),
         ("SDN switch", "live traffic checked; attacker blocked", "coral", CORAL)]
n = len(steps)
gap = 230000
cw = (CW - (n - 1) * gap) // n
y = CY + 650000
for i, (h, b, tn, ac) in enumerate(steps):
    x = CX + i * (cw + gap)
    chip(s, x, y, cw, 1900000, i + 1, h, b, tint=tn, accent=ac, size=14, head_size=15)
    if i < n - 1:
        arrow(s, x + cw + 15000, y + 950000, x + cw + gap - 15000, y + 950000)
# phase brackets
bw = 4 * cw + 3 * gap
textbox(s, CX, CY + 100000, bw, 400000, [[("Phase A: training (offline, federated)", True)]], size=15,
        align=PP_ALIGN.CENTER, color=NAVY)
textbox(s, CX + 3 * (cw + gap), CY + 100000, 2 * cw + gap, 400000, [[("Phase B: protection (live)", True)]],
        size=15, align=PP_ALIGN.CENTER, color=CORAL)
textbox(s, CX, y + 2150000, CW, 900000,
        ["Raw traffic never leaves a site: only model updates travel to the server. "
         "Phase A produces a saved model bundle; Phase B loads it on an emulated network (Mininet + Open vSwitch)."],
        size=15, color=MUTED)
notes(s, "The big picture has two phases. In Phase A, ten sites each train a copy of the detector on their "
         "own traffic and send only the model updates to the server. The server checks each update, throws out "
         "suspicious ones and combines the rest. The trained detector is saved. In Phase B we load it on an "
         "emulated network: traffic is checked live, and when an attack is found the switch gets a rule to block it.")

# =============================================================== 8 Detailed design: two checks
s = S[7]
set_title(s, "Detailed Design: Two Checks per Packet")
remove_body(s)
bw, bh = 2650000, 1150000
xA = CX
xB = CX + 3300000
xC = CX + 7300000
yT, yM, yB = CY + 100000, CY + 1500000, CY + 2950000
card(s, xA, yM, 2300000, bh, "Network traffic", ["packets + connection features"], tint="grey", accent=MUTED, size=13, head_size=16)
card(s, xB, yT + 200000, bw, bh + 150000, "Check 1: Known attack?", ["LightGBM classifier names the attack type"],
     tint="navy", accent=NAVY, size=13, head_size=16)
card(s, xC, yT + 200000, 3215600, bh, "Attack type", ["e.g. “SQL injection” (≥ 70% sure)"],
     tint="coral", accent=CORAL, size=13, head_size=16)
card(s, xB, yB - 100000, bw, bh + 150000, "Check 2: Looks normal?", ["autoencoder compares it to this site's normal traffic"],
     tint="teal", accent=TEAL, size=13, head_size=16)
card(s, xC, yB - 450000, 3215600, 950000, "Anomalous", ["possible new (zero-day) attack"], tint="gold", accent=GOLD, size=13, head_size=16)
card(s, xC, yB + 650000, 3215600, 700000, "Normal", [], tint="grey", accent=MUTED, size=13, head_size=16)
arrow(s, xA + 2300000, yM + bh // 2, xB, yT + 200000 + (bh + 150000) // 2)
arrow(s, xB + bw, yT + 200000 + bh // 2, xC, yT + 200000 + bh // 2, color=CORAL)
label(s, xB + bw, yT - 60000, xC - xB - bw, "yes, sure", color=CORAL)
arrow(s, xB + bw // 2, yT + 200000 + bh + 150000, xB + bw // 2, yB - 100000, color=TEAL)
label(s, xB + bw // 2 + 60000, yM + 350000, 1500000, "no / unsure", color=TEAL, align=PP_ALIGN.LEFT)
arrow(s, xB + bw, yB + 150000, xC, yB + 25000, color=GOLD)
label(s, xB + bw, yB - 330000, xC - xB - bw, "too different", color=GOLD)
arrow(s, xB + bw, yB + 700000, xC, yB + 1000000, color=MUTED)
label(s, xB + bw, yB + 900000, xC - xB - bw, "matches normal", color=MUTED)
notes(s, "Every packet goes through two checks. Check 1 is a LightGBM classifier that knows the 14 attack "
         "types; if it is at least 70% sure it's an attack, that is the answer. Otherwise Check 2 runs: an "
         "autoencoder that has learned what this site's normal traffic looks like. If the packet is too "
         "different from normal, it is flagged as anomalous, which is how we catch attacks nobody trained us on.")

# =============================================================== 9 Detailed design: safe training
s = S[8]
set_title(s, "Detailed Design: Training Safely Together")
remove_body(s)
st = [("Send model", "server sends the current detector to all 10 sites"),
      ("Learn locally", "each site trains on its own traffic, which never leaves"),
      ("Trust check", "server compares each site's change with the group's typical change"),
      ("Combine", "suspicious changes are dropped; the rest are averaged robustly")]
cw = (CW - 3 * 220000) // 4
for i, (h, b) in enumerate(st):
    x = CX + i * (cw + 220000)
    chip(s, x, CY + 50000, cw, 1750000, i + 1, h, b, tint=["gold", "teal", "coral", "navy"][i],
         accent=[GOLD, TEAL, CORAL, NAVY][i], size=14, head_size=16)
    if i < 3:
        arrow(s, x + cw + 10000, CY + 925000, x + cw + 210000, CY + 925000)
label(s, CX, CY + 1850000, CW, "repeated for 20 rounds", color=MUTED, size=13)
card(s, CX, CY + 2300000, CW, 1600000, "The trust check in one line",
     ["Like a teacher comparing homework: if one student's answer points the opposite way to the class's typical "
      "answer, or keeps disagreeing round after round, it is set aside. Large answers are also capped so one "
      "student can't dominate."],
     tint="grey", accent=NAVY, size=16, head_size=17)
notes(s, "This is federated learning with a trust filter. Each round the server sends the current model out, "
         "each site trains on its own data, and sends back only how its model changed. The server compares "
         "every change with the typical change across all sites using cosine similarity. A change that points "
         "the opposite way, is an outlier, or comes from a site that keeps disagreeing is dropped. The rest are "
         "size-limited and combined with a trimmed mean, which ignores the extremes.")

# =============================================================== 10 Implementation: tools
s = S[9]
remove_body(s)
rows = [["Part", "Built with"],
        ["Data preparation", "Python, pandas: cleaning, dataset repairs, new features"],
        ["Check 1: classifier", "LightGBM (gradient-boosted trees)"],
        ["Check 2: anomaly detector", "PyTorch autoencoder, one per site"],
        ["Federated training", "Flower: 1 server + 10 real client processes"],
        ["Network + blocking", "Mininet, Open vSwitch, os-ken OpenFlow controller"],
        ["Live traffic features", "TShark + tcpreplay (replays real attack captures)"],
        ["Monitoring", "Streamlit live dashboard"],
        ["Quality", "224 automated tests; one config file; repeatable runs"]]
table(s, CX, CY + 50000, CW, rows, [3100000, CW - 3100000], size=15, row_h=420000, left_all=True)
textbox(s, CX, CY + 50000 + 9 * 420000 + 120000, CW, 400000,
        ["Ran on: Ubuntu VM (UTM) on a MacBook Pro M5, 4 CPUs, 7 GB RAM, all free and open-source software"],
        size=13, color=MUTED)
notes(s, "These are the tools for each part. Everything is open source and runs on one laptop inside a virtual machine.")

# =============================================================== 11 Implementation: steps
s = S[10]
set_title(s, "Implementation: Step by Step")
remove_body(s)
steps = [("Load dataset", "2.2 million labelled packets, 15 classes"),
         ("Fix dataset errors", "label-leak artefact; broken MITM rows"),
         ("Build features", "service port, content, connection behaviour"),
         ("Train classifier", "LightGBM on the server's labelled set"),
         ("Split into 10 sites", "each site gets very different traffic"),
         ("Federated rounds", "local training + trust check, 20 rounds"),
         ("Evaluate", "accuracy, sabotage tests, unseen-attack tests"),
         ("Live demo", "replay attack → detect → block on switch")]
cw = (CW - 3 * 200000) // 4
for i, (h, b) in enumerate(steps):
    x = CX + (i % 4) * (cw + 200000)
    y = CY + (i // 4) * 2050000
    chip(s, x, y, cw, 1800000, i + 1, h, b, tint=["navy", "navy", "navy", "gold", "teal", "teal", "coral", "coral"][i],
         accent=[NAVY, NAVY, NAVY, GOLD, TEAL, TEAL, CORAL, CORAL][i], size=14, head_size=15)
    if i % 4 < 3:
        arrow(s, x + cw + 10000, y + 900000, x + cw + 190000, y + 900000)
notes(s, "Eight steps from raw data to a blocked attacker. Steps 1 to 3 prepare the data, including fixing two "
         "errors we found in the public dataset. Step 4 trains the classifier. Steps 5 and 6 are federated "
         "training across ten simulated sites. Step 7 evaluates everything, and step 8 is the live demo.")

# =============================================================== 12 Implementation: accuracy
s = S[11]
set_title(s, "Implementation: How We Raised Accuracy")
remove_body(s)
textbox(s, CX, CY - 80000, CW, 800000,
        [[("The problem: ", True), ("in web attacks like SQL injection and XSS, only 5–17% of packets carry any "
          "content. The rest are identical “acknowledgement” packets, the same for every attack, so "
          "the classifier could not tell them apart.", False)]], size=17)
cw = (CW - 2 * 250000) // 3
y = CY + 950000
card(s, CX, y, cw, 2200000, "1. Which service?",
     ["The server port of each connection: web (80), MQTT (1883), etc."], tint="navy", accent=NAVY, size=15)
card(s, CX + cw + 250000, y, cw, 2200000, "2. What was sent?",
     ["Numbers describing the content: length, randomness, SQL or script keywords, uploads, logins."],
     tint="teal", accent=TEAL, size=15)
card(s, CX + 2 * (cw + 250000), y, cw, 2200000, "3. How did the conversation behave?",
     ["Group packets into connections; every packet gets its connection's totals and rates."],
     tint="coral", accent=CORAL, size=15)
textbox(s, CX, y + 2350000, CW, 600000,
        [[("+ rare attack types weighted higher.  ", True),
          ("We never use IP addresses or timestamps, since those would let the model cheat.", False)]], size=15)
notes(s, "This is the main improvement this semester. The classifier was stuck at about 0.89 macro F1 because "
         "most packets of web attacks carry no content: they are empty acknowledgements that look the same for "
         "every attack. We added three kinds of information: which service a connection is for, numbers "
         "describing what was sent, and how the whole connection behaved. Then each empty packet carries what "
         "its connection did. We also weighted rare attack types more. We deliberately never used IP addresses "
         "or timestamps, because in this dataset they would reveal the answer.")

# =============================================================== 13 Results: dataset & testing
s = S[12]
set_title(s, "Results: Dataset and How We Tested")
remove_body(s)
rows = [["Edge-IIoTset", "Value"], ["Packets", "2.2 million"], ["After cleaning", "1.99 million"],
        ["Classifier trained on", "1.43 million"], ["Tested on (unseen)", "397 thousand"],
        ["Classes", "15 (Normal + 14 attacks)"], ["Normal traffic", "71%"], ["Rarest attacks", "MITM, Fingerprinting"]]
table(s, CX, CY + 50000, 4600000, rows, [2300000, 2300000], size=14, row_h=390000)
card(s, CX + 4900000, CY + 50000, CW - 4900000, 2600000, "A strict test",
     ["We test on whole connections the model has never seen, so it cannot pass by memorising them.",
      "Repeated with 3 different random seeds.",
      [("Accuracy ", True), ("= share of correct answers.  ", False), ("Macro F1 ", True),
       ("= average score over all 15 classes, so rare attacks count as much as common ones.", False)]],
     tint="grey", accent=NAVY, size=15)
textbox(s, CX + 4900000, CY + 2800000, CW - 4900000, 900000,
        [[("Fixed first: ", True), ("a formatting error in the public dataset gave away the answer (one column "
          "alone separated normal from attack perfectly), and the MITM rows were in the wrong columns.", False)]],
        size=14)
notes(s, "The dataset is Edge-IIoTset: about two million packets after cleaning, fifteen classes, 71% normal "
         "traffic. The classifier is trained on 1.43 million of them and tested on 397 thousand it never saw. "
         "The federated part uses a smaller share, about 125 thousand rows, so that the 150 or so experiment runs finish in time. "
         "We test strictly, on whole connections never seen in training, and repeat with three seeds. "
         "Before any of this we fixed two errors in the public data. One of them was a formatting difference "
         "that alone separated normal from attack traffic perfectly, which would have made any model look "
         "better than it really is.")

# =============================================================== 14 Results: accuracy
s = S[13]
set_title(s, "Results: Accuracy Target Met")
remove_body(s)
picture(s, PF / "accuracy_progression.png", CX, CY - 100000, 7300000, CH - 150000)
x = CX + 7550000
stat(s, x, CY + 50000, 3000000, "99.7%", "accuracy (was 96.4%)", NAVY)
stat(s, x, CY + 1450000, 3000000, "0.983", "macro F1 (was 0.889)", TEAL)
textbox(s, x, CY + 2850000, 2950000, 1500000,
        ["Target: ≥ 95% and ≥ 0.95.",
         "Same result with 3 seeds (0.983–0.985).",
         "Still 99.7% / 0.979 when trained on only 5% of the data."], size=14, color=MUTED)
notes(s, "This is the headline result. With the original features, accuracy was 96.4% but macro F1 only 0.889. "
         "Each new kind of information pushes it up; the connection features give the big jump. The final "
         "classifier reaches 99.7% accuracy and 0.983 macro F1 on connections it never saw, well above the 95% "
         "target. It holds across three seeds, and even when trained on only 5% of the data, which is what our "
         "server actually holds.")

# =============================================================== 15 Results: confusion matrix
s = S[14]
set_title(s, "Results: Confusion Matrix (Final Classifier)")
remove_body(s)
picture(s, PF / "confusion_final.png", CX - 200000, CY - 200000, 6500000, CH + 250000)
x = CX + 6550000
card(s, x, CY, CW - 6550000 + 200000, 4100000, "How to read it",
     ["Rows = the real attack, columns = what we predicted. A perfect model is a dark diagonal.",
      [("Almost perfect: ", True), ("11 of 14 classes are 0.98–1.00.", False)],
      [("Small mix-ups: ", True), ("Password ↔ DDoS HTTP (both hit the same web server), "
                                   "Ransomware → Backdoor (same port).", False)],
      "MITM is a single connection, so it can't appear in this strict test (random split: F1 0.99)."],
     tint="grey", accent=NAVY, size=14, head_size=16)
notes(s, "The confusion matrix shows where the model is right and wrong. Each row is the real class and each "
         "column the prediction, so a perfect model is a dark diagonal. Ours is almost entirely diagonal. The "
         "only visible mix-ups are between Password attacks and HTTP floods, which both send web requests to the "
         "same server, and Ransomware sometimes taken for Backdoor because they use the same port.")

# =============================================================== 16 Results: per class
s = S[15]
set_title(s, "Results: Every Attack Type Improved")
remove_body(s)
picture(s, PF / "per_class_f1.png", CX, CY - 100000, 7100000, CH - 50000)
textbox(s, CX + 7300000, CY + 200000, CW - 7300000, 3800000,
        [[("Biggest gains", True)],
         "Uploading 0.76 → 1.00",
         "DDoS HTTP 0.76 → 0.97",
         "SQL injection 0.80 → 1.00",
         "Password 0.84 → 0.97",
         "XSS 0.85 → 0.98",
         "Fingerprinting 0.68 → 0.93",
         "",
         "Exactly the web and rare attacks that were weak before."], size=15)
notes(s, "Per attack type, every class is now above 0.92 F1. The largest gains are exactly the web "
         "attacks that used to be confused with each other, plus Fingerprinting, the rarest class, which "
         "benefited from class weighting.")

# =============================================================== 17 Results: zero-day
s = S[16]
set_title(s, "Results: Catching Attacks Never Seen Before")
remove_body(s)
picture(s, PF / "zero_day.png", CX, CY - 100000, 6900000, CH - 50000)
x = CX + 7100000
stat(s, x, CY + 50000, 3300000, "0.94", "detection with both checks (was 0.74)", TEAL)
stat(s, x, CY + 1400000, 3300000, "0.80", "classifier alone (was 0.53)", NAVY)
textbox(s, x, CY + 2750000, CW - 7100000, 1500000,
        ["Each attack type was hidden from training, then tested.",
         "Password 0.44 → 0.97, XSS 0.52 → 0.99.",
         "Worse: MITM 0.89 → 0.69."], size=14, color=MUTED)
notes(s, "To test unseen attacks, we hid each attack type completely from training, one at a time, and then "
         "checked whether it was still caught. With the new features, the classifier alone catches 80% on average; "
         "with the anomaly check added it is 94%, up from 74% before the new features. The web attacks improved the "
         "most, for example Password from 44% to 97%. One honest exception: MITM dropped from 89% to 69%, because its "
         "single connection now looks fairly ordinary to the anomaly check.")

# =============================================================== 18 Results: poisoning
s = S[17]
set_title(s, "Results: Resisting Sabotage")
remove_body(s)
picture(s, PF / "poisoning_sweep.png", CX, CY - 150000, CW, 3000000)
card(s, CX, CY + 2950000, CW, 1250000, "What it shows",
     ["Detection stays at 99.7–100% with up to 50% malicious sites, and new-attack detection at 90–94% up to 40%. "
      "Without the trust check (plain averaging) the anomaly check is ruined at 30%. At 50% attackers become the majority "
      "and the check fails, a known limit of this kind of defence."],
     tint="grey", accent=NAVY, size=14, head_size=15)
notes(s, "Here some of the ten sites are attackers that send poisoned updates. Detection stays at almost 100%, and "
         "detection of new attacks stays above 90% up to 40% attackers. On the right: only 10-12% of attacker updates get "
         "through at 20-30%, and 36% at 40%. Without our trust check, "
         "plain federated averaging broke at 30%. At 50% the attackers are the majority, so the 'typical' "
         "update is theirs and the check fails, which is the expected limit of any median-based defence.")

# =============================================================== 19 Results: live demo
s = S[18]
set_title(s, "Results: Live Demo (Detect and Block)")
remove_body(s)
st = [("Replay", "real Backdoor attack capture, 24,914 packets, into the emulated network"),
      ("Detect", "classified as Backdoor with 99.7% confidence"),
      ("Decide", "confidence ≥ 85% → block"),
      ("Block", "drop rule installed on the switch and read back to confirm")]
cw = (CW - 3 * 220000) // 4
for i, (h, b) in enumerate(st):
    x = CX + i * (cw + 220000)
    chip(s, x, CY + 50000, cw, 1900000, i + 1, h, b, tint=["grey", "navy", "gold", "coral"][i],
         accent=[MUTED, NAVY, GOLD, CORAL][i], size=14, head_size=16)
    if i < 3:
        arrow(s, x + cw + 10000, CY + 1000000, x + cw + 210000, CY + 1000000)
card(s, CX, CY + 2200000, CW, 900000, "Rule on the switch",
     ["priority=100, ip, nw_src=10.0.0.1  actions=drop"], tint="grey", accent=CORAL, size=16, head_size=15)
textbox(s, CX, CY + 3250000, CW, 900000,
        ["Real 10-site federated run: 0.999 attack detection (was 0.889), 3.5% false alarms. 24,669 of 24,914 packets flagged.  "
         "Limitation: the decision is made after the capture is analysed, not packet by packet."], size=14, color=MUTED)
notes(s, "Finally the live demo. We replayed a real Backdoor attack into the emulated network. The detector "
         "classified it as Backdoor with 99.7% confidence, chose to block, and installed a drop rule on the "
         "switch, which we read back from the switch itself to confirm. One honest limitation: right now the "
         "decision is made after the whole capture is analysed, not packet by packet.")

# =============================================================== 20 Conclusion
s = S[19]
bullets(s, [
    [("Accuracy target met: ", True), ("99.7% accuracy and 0.983 macro F1 on 397k unseen packets (was 96.4% / 0.889)", False)],
    [("Whole system improved: ", True), ("real 10-site run 0.999 detection (was 0.889)", False)],
    [("Catches new attacks: ", True), ("0.94 vs 0.80 detection of never-seen attack types (was 0.74 / 0.53)", False)],
    [("Resists sabotage: ", True), ("steady with up to 40% malicious sites", False)],
    [("Acts automatically: ", True), ("detected attacker blocked on the switch, verified", False)],
    [("Honest data: ", True), ("found and fixed two errors in a widely used public dataset", False)],
    [("What's novel: ", True), ("we found no published system combining all five parts, and the dataset fixes", False)],
    [("Project complete: ", True), ("every planned phase done and verified end to end; paper being written", False)],
], size=18, space=8)
notes(s, "To conclude: the project is complete. We met the accuracy target with a strict test, the second check catches attacks never "
         "seen before, the training resists sabotage up to 40% bad sites, and detections turn into verified "
         "blocking rules. We also found and fixed errors in a popular public dataset. Our searches found no "
         "published system that combines all five parts, though that is based on targeted searches, not a full "
         "systematic review.")

# =============================================================== 21 Future
s = S[20]
bullets(s, [
    "Apply weight pruning to shrink the model and its updates (Objective 3)",
    "Block attacks while they are still happening (decide after the first few packets)",
    "Test smarter attackers, and more than 50% bad sites",
    "Repeat every federated experiment with several seeds",
    "Test on a second dataset that includes normal web traffic",
    "Deploy on real edge devices and a hardware switch",
], size=19, space=10)
notes(s, "Next steps: prune the model to cut communication further, make blocking "
         "happen while an attack is still in progress, test smarter attackers, and validate on a second dataset.")

# =============================================================== 22 Papers
s = S[21]
set_title(s, "Papers Published")
bullets(s, [
    [("Status: ", True), ("paper in preparation (draft in progress)", False)],
    [("Working title: ", True), ("FL-IDS: Federated Learning-Based Intrusion Detection System for IoT/IIoT", False)],
    [("Venue: ", True), ("not yet submitted", False)],
], size=20, space=12)
notes(s, "Our paper is in preparation. All the experiments are complete, so we are now writing it up for submission.")

# =============================================================== 23 References
s = S[22]
bullets(s, [
    "M. A. Ferrag et al., “Edge-IIoTset: A new comprehensive realistic cyber security dataset of IoT and IIoT applications for centralized and federated learning,” IEEE Access, vol. 10, pp. 40281–40306, 2022.",
    "V. Mothukuri et al., “Federated-learning-based anomaly detection for IoT security attacks,” IEEE IoT Journal, vol. 9, no. 4, 2022.",
    "B. Li et al., “DeepFed: Federated deep learning for intrusion detection in industrial cyber–physical systems,” IEEE TII, vol. 17, no. 8, 2021.",
    "X. Cao, M. Fang, J. Liu, N. Z. Gong, “FLTrust: Byzantine-robust federated learning via trust bootstrapping,” NDSS, 2021.",
    "J. Xu et al., “Byzantine-robust federated learning through collaborative malicious gradient filtering (SignGuard),” IEEE ICDCS, 2022.",
    "H. Zhang et al., “A two-stage intrusion detection method based on LightGBM and autoencoder,” Math. Biosci. Eng., vol. 20, no. 4, 2023.",
    "Z. Abou El Houda, A. S. Hafid, L. Khoukhi, “MiTFed: … federated learning using SDN and blockchain,” IEEE TNSE, vol. 10, no. 4, 2023.",
    "J. L. Hernandez-Ramos et al., “Intrusion detection based on federated learning: a systematic review,” ACM Computing Surveys, vol. 57, no. 12, 2025.",
    "I. Sharafaldin, A. H. Lashkari, A. A. Ghorbani, “Toward generating a new intrusion detection dataset and intrusion traffic characterization,” ICISSP, 2018.",
], size=13, space=3)

# =============================================================== 24 Thank you
notes(S[23], "Thank you. We're happy to take questions.")

prs.save(OUT)
print("saved", OUT)
