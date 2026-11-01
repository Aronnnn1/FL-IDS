# Project deliverables

Documents produced from this repository's results (16 October 2026).

| Folder | Contents |
|---|---|
| `presentation/` | Review presentation (`.pptx`, BMSCE PP2 format) and a PDF render |
| `report/` | Project report: LaTeX source (`main.tex`, `ch*.tex`, logos, figures) and the compiled `FL-IDS_Project_Report.pdf`. Build with `tectonic main.tex` |
| `explainers/` | `mp-expl.pdf` (the project in plain language) and `website-explained.pdf` (the results site explained section by section), with their HTML sources |
| `scripts/` | `charts.py` (result charts from `results/` and `experiments/accuracy/results/`), `diagrams.py` (architecture diagrams), `build_pres.py` (fills the presentation template) |

Numbers in all of these come from `results/`, `results/extended/` and
`experiments/accuracy/results/`; `PAPER_NOTES.md` gives the source of each.

## Update 2026-11-01

- `report/` now has a section on the real 20-client runs, repeat seeds and run timing (Chapter 5); the PDF was rebuilt in the VM with
  `xelatex main.tex` (run three times; needs `texlive-xetex`, `texlive-latex-extra`, `texlive-fonts-extra`, `tex-gyre`).
- `presentation/` has two added slides (19 "Scaling Up and Repeating", 21 "One Whole Run, Timed"), added in place by
  `scripts/add_new_result_slides.py` because the deck's original builder input was lost.
- The explainer PDFs were not regenerated.

## Update 2026-11-01 (later)

- `report/` Chapter 5 gained a section on the follow-up experiments (more seeds, an adaptive attacker, pruning, a time-ordered split); the PDF is 65 pages.
- `presentation/` has a third added slide (22, "Pruning and Smarter Attackers", added by `scripts/add_followup_slide.py`); the future-work slide no longer lists weight pruning as undone. The deck has 27 slides.
- `explainers/` were regenerated with WeasyPrint (`mp-expl.pdf` 9 pages, `website-explained.pdf` 23 pages) after adding the November results. They were built with Chrome before, so spacing differs slightly.
- `scripts/new_figures.py` produces the figures added to `report/figures/` (trust trajectories, partition heatmap, reconstruction error, clip comparison, placeholder AUROC, Phase B timeline).
