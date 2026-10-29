"""Architecture / design / methodology diagrams for the FL-IDS report and slides."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

NAVY = "#1E2761"
TEAL = "#028090"
CORAL = "#D64550"
GOLD = "#E0A526"
GREY = "#5B6770"
LIGHT = {"navy": "#E3E7F4", "teal": "#DDF1F2", "coral": "#F9E1E3", "gold": "#FBF0D9", "grey": "#EEF0F2"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})


def box(ax, x, y, w, h, text, color=NAVY, fill="navy", size=10, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=LIGHT[fill], ec=color, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color="#1b1b1b",
            fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, color=GREY, text=None, style="-|>", ls="-", tx=0, ty=0.08):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14, color=color,
                                 lw=1.5, linestyle=ls, shrinkA=2, shrinkB=2))
    if text:
        ax.text((x1 + x2) / 2 + tx, (y1 + y2) / 2 + ty, text, ha="center", va="bottom", fontsize=8.5, color=color)


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def high_level():
    fig, ax = canvas(12, 6.2)
    # Phase A frame
    ax.add_patch(FancyBboxPatch((0.2, 0.3), 7.6, 5.6, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="white", ec=NAVY, lw=1.2, ls="--"))
    ax.text(0.45, 5.6, "Phase A: offline federated training", fontsize=12, fontweight="bold", color=NAVY)
    ax.add_patch(FancyBboxPatch((8.2, 0.3), 3.6, 5.6, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="white", ec=TEAL, lw=1.2, ls="--"))
    ax.text(8.4, 5.6, "Phase B: live mitigation", fontsize=12, fontweight="bold", color=TEAL)

    box(ax, 0.5, 4.2, 2.3, 1.0, "Edge-IIoTset\n2.2M packets,\n15 classes", fill="grey", color=GREY, size=9.5)
    box(ax, 3.2, 4.2, 2.3, 1.0, "Data pipeline\nclean, repair, features,\nDirichlet split", size=9)
    box(ax, 5.8, 4.2, 1.8, 1.0, "Server calibration\nset (5%)", size=9, fill="gold", color=GOLD)
    arrow(ax, 2.8, 4.7, 3.2, 4.7)
    arrow(ax, 5.5, 4.7, 5.8, 4.7)

    box(ax, 5.6, 2.35, 2.0, 1.35, "Flower server\nLightGBM classifier\n+ trust filter\n+ trimmed mean", size=9,
        fill="gold", color=GOLD, bold=False)
    arrow(ax, 6.7, 4.2, 6.6, 3.7)
    for i, yy in enumerate([3.45, 2.25, 1.05]):
        box(ax, 0.5, yy - 0.3, 2.5, 0.8, f"Client {['1', '2', '10'][i]}\nlocal traffic + autoencoder", size=8.5,
            fill="teal", color=TEAL)
    ax.text(1.75, 1.7, "...", ha="center", fontsize=16, color=TEAL)
    arrow(ax, 3.2, 4.2, 2.0, 3.95, color=GREY)
    for yy in [3.45, 2.25, 1.05]:
        arrow(ax, 3.0, yy + 0.15, 5.6, 3.0 + (yy - 2.25) * 0.2, color=TEAL)
        arrow(ax, 5.6, 2.85 + (yy - 2.25) * 0.2, 3.0, yy - 0.05, color=GOLD)
    ax.text(4.3, 3.95, "AE weight updates", fontsize=8.5, color=TEAL, ha="center")
    ax.text(4.3, 0.55, "global AE + LightGBM model", fontsize=8.5, color="#9a6d00", ha="center")

    box(ax, 5.6, 0.6, 2.0, 0.9, "Model bundle\n(manifest.json)", size=9)
    arrow(ax, 6.6, 2.35, 6.6, 1.5)

    box(ax, 8.5, 4.2, 3.0, 1.0, "Mininet + Open vSwitch\nreplayed .pcap (tcpreplay)", size=9, fill="grey", color=GREY)
    box(ax, 8.5, 2.75, 3.0, 1.0, "tshark features\n-> cascade verdict", size=9, fill="teal", color=TEAL)
    box(ax, 8.5, 1.3, 3.0, 1.0, "os-ken controller\nOpenFlow 1.3: drop / meter", size=9, fill="coral", color=CORAL)
    arrow(ax, 10.0, 4.2, 10.0, 3.75)
    arrow(ax, 10.0, 2.75, 10.0, 2.3, text="REST bridge", tx=0.55, ty=-0.1)
    arrow(ax, 8.5, 1.8, 8.5 - 0.0, 4.4, color=CORAL, style="-|>", ls=":")
    ax.text(8.3, 3.1, "flow rule", fontsize=8.5, color=CORAL, rotation=90, ha="center")
    arrow(ax, 7.6, 1.05, 8.5, 3.1, color=NAVY, text="load", tx=-0.15, ty=0.0)
    save(fig, "high_level_design")


def cascade():
    fig, ax = canvas(11, 4.2)
    box(ax, 0.2, 1.6, 1.8, 1.0, "Packet / flow\nfeatures", fill="grey", color=GREY)
    box(ax, 2.6, 1.6, 2.2, 1.0, "Stage 1\nLightGBM classifier", bold=True)
    arrow(ax, 2.0, 2.1, 2.6, 2.1)
    box(ax, 5.6, 2.9, 2.3, 0.95, "Known attack type\n(confidence = p)", fill="coral", color=CORAL)
    arrow(ax, 4.8, 2.35, 5.6, 3.3, color=CORAL, text="attack, p >= 0.7", tx=-0.95, ty=0.05)
    box(ax, 5.6, 0.45, 2.3, 1.15, "Stage 2\nclient autoencoder\nerror e vs threshold t", fill="teal", color=TEAL)
    arrow(ax, 4.8, 1.85, 5.6, 1.1, color=TEAL, text="normal or p < 0.7", tx=-0.55, ty=-0.35)
    box(ax, 8.7, 1.35, 2.1, 0.85, "anomalous\nconf = clip(e/t - 1)", fill="gold", color=GOLD, size=9)
    box(ax, 8.7, 0.1, 2.1, 0.8, "benign", fill="grey", color=GREY)
    arrow(ax, 7.9, 1.2, 8.7, 1.75, color=GOLD, text="e > t", tx=-0.05, ty=0.05)
    arrow(ax, 7.9, 0.85, 8.7, 0.5, color=GREY, text="e <= t", tx=0.0, ty=-0.33)
    ax.text(5.6, 4.05, "t = 97th percentile of the client's own benign validation error, recomputed every round",
            fontsize=9, color=GREY)
    save(fig, "cascade_rule")


def fl_round():
    fig, ax = canvas(12, 4.6)
    steps = [
        ("1. Broadcast", "global AE weights\n+ LightGBM model", "gold", GOLD),
        ("2. Local filter", "LightGBM keeps rows\nit passes as normal", "navy", NAVY),
        ("3. Local train", "AE: 5 epochs, Adam,\nMSE; new threshold", "teal", TEAL),
        ("4. Trust filter", "cosine vs median\ndelta: exclude MAD\noutlier, cos<0,\nEMA trust<0.5", "coral", CORAL),
        ("5. Aggregate", "norm clip 2x median,\n15% trimmed mean", "gold", GOLD),
        ("6. Boost update", "every 3 rounds:\n+50 LightGBM trees\non confirmed alerts", "navy", NAVY),
    ]
    w, gap = 1.75, 0.22
    for i, (t, d, f, c) in enumerate(steps):
        x = 0.2 + i * (w + gap)
        box(ax, x, 1.4, w, 1.7, "", fill=f, color=c)
        ax.text(x + w / 2, 2.75, t, ha="center", fontsize=10, fontweight="bold")
        ax.text(x + w / 2, 1.95, d, ha="center", va="center", fontsize=8.6)
        if i < len(steps) - 1:
            arrow(ax, x + w, 2.25, x + w + gap, 2.25)
    ax.add_patch(FancyArrowPatch((0.2 + 5 * (w + gap) + w / 2, 1.4), (0.2 + w / 2, 1.4),
                                 connectionstyle="arc3,rad=-0.12", arrowstyle="-|>", mutation_scale=14,
                                 color=GREY, lw=1.4))
    ax.text(6.0, 0.05, "repeat for 20 rounds  (10 clients, Dirichlet alpha = 0.3)", ha="center", fontsize=9.5,
            color=GREY)
    ax.text(0.2, 3.6, "Server", fontsize=9, color=GOLD, fontweight="bold")
    ax.text(0.2 + (w + gap), 3.6, "Clients", fontsize=9, color=TEAL, fontweight="bold")
    ax.text(0.2 + 3 * (w + gap), 3.6, "Server", fontsize=9, color=GOLD, fontweight="bold")
    ax.set_ylim(-0.1, 4.0)
    save(fig, "fl_round")


def methodology_flow():
    fig, ax = canvas(7.2, 11.5)
    items = [
        ("Start: Edge-IIoTset CSV + .pcap captures", "grey", GREY),
        ("Repair MITM rows from the authors' pcap;\ncanonicalise '0'/'0.0' placeholders", "navy", NAVY),
        ("Derive features: service port, payload/URI\ncontent, flow aggregates (60 s idle, 120 s active)", "navy", NAVY),
        ("Drop exact duplicates; one-hot encode", "navy", NAVY),
        ("Split: 5% server calibration set;\nrest -> 10 clients by Dirichlet(0.3)", "gold", GOLD),
        ("Train LightGBM on calibration set", "gold", GOLD),
        ("20 federated rounds: filter -> local AE ->\ntrust filter -> trimmed mean -> LightGBM update", "teal", TEAL),
        ("Evaluate: accuracy/F1 (random + flow-grouped),\nablation, poisoning sweep, zero-day", "teal", TEAL),
        ("Save model bundle", "navy", NAVY),
        ("Phase B: replay pcap in Mininet -> tshark ->\ncascade -> OpenFlow rule -> verify flow table", "coral", CORAL),
        ("End", "grey", GREY),
    ]
    h, gap = 0.78, 0.22
    y = 11.5 - 0.3 - h
    for i, (t, f, c) in enumerate(items):
        box(ax, 0.4, y, 6.4, h, t, fill=f, color=c, size=9.2, bold=i in (0, len(items) - 1))
        if i < len(items) - 1:
            arrow(ax, 3.6, y, 3.6, y - gap)
        y -= h + gap
    save(fig, "methodology_flowchart")


if __name__ == "__main__":
    high_level()
    cascade()
    fl_round()
    methodology_flow()
    print("ok")
