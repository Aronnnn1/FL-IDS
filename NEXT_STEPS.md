# NEXT_STEPS.md: handover for the next session

Written 2026-11-02. Read this first, then `CLAUDE.md` and `PAPER_NOTES.md` (§8.15 holds the full-dataset results). State at time of writing: GitHub `main` = commit `afd23e0` plus this file; 244 tests pass, 1 skipped.

## 1. The project in one paragraph
FL-IDS is a federated-learning intrusion detection system for IoT/IIoT networks (BMSCE CSE major project; guide Mr. Syed Akram). It is a two-stage cascade: a LightGBM classifier on the server, then a per-site autoencoder as a backstop for unseen attacks. Flower federated learning with a trust filter (median-delta cosine/MAD/EMA trust, norm clip, 15% trimmed mean) resists cheating sites. An SDN layer (Mininet, OVS, os-ken) replays attack captures and installs drop rules. Data: Edge-IIoTset, 2,219,201 rows, 1,985,768 unique usable rows, 130 features, 15 classes. A paper is planned, so every number must hold up to reviewers.

## 2. Working rules from the owner (do not break)
- **All work stays in the VM.** The owner does not want malicious data or any virus on the Windows host. Everything (files, results, training) runs in the VMware VM at `D:\FL-IDS-VM`: `ssh fl-ids-vm`, user `flids`, repo `~/FL-IDS-clean`. No Samba, shared folder or mapped drive. Pull back text only (logs, numbers) unless asked. The SSH port tunnel is optional and off by default. Host copies in `D:\FL-IDS-VM\data` stay.
- Do not assume; ask when in doubt. Every number must come from a real run and be tagged. Update `PAPER_NOTES.md` with each piece of work. Be honest about limitations. Keep everything pushed to GitHub.
- The owner finds technical jargon hard. **Explain results in plain words.**
- VM: 20 vCPUs, 48 GB RAM (old settings in `fl-ids.vmx.bak`). Memory budget: about 4.4 GB per in-process job, about 28 GB for a 20-client real run. **Never run 20-client real runs alongside other jobs** (an out-of-memory crash on 2026-11-01 killed everything). Max 9 in-process workers.
- Use locally written files plus `scp` rather than long ssh heredocs (quoting broke repeatedly).

## 3. Decisions already made (2026-11-01 / 02)
1. Train and test the whole pipeline (federated, aggregation, zero-day, live replays) on all ~1.99M usable rows.
2. **Keep conversations (flows) together when splitting**, even if scores drop. Flow ids come from `assign_flows` (342,814 flows).
3. Download all attack captures into the VM only (done: all 14 now present).
4. **Keep the older 60k-pool, row-split results as a labelled comparison** so we can go back to them. They stay in `PAPER_NOTES.md` §8.1 to §8.14 and `results/seeds`, `results/real_runs`.
5. Mitigation limits stay honest: replay uses the dataset's own recordings, so it is a demonstration, not a held-out test.

## 4. What exists (full-pool run, all pushed)
- Six real runs: 10 and 20 clients, seeds 42/43/44 (`results/full/<tag>/`, tags `c10_s42` … `c20_s44`), 77 experiment jobs, Phase B on all 14 captures.
- Headline numbers: known attacks 99.56–99.89% micro recall (not inflated by the old row split); packet false alarms 2.5–16.3%, connection-level 0.3–1.0%, typical site about 3%; zero-day cascade mean 0.910/0.944/0.895 (60k: 0.943/0.952/0.952); trust-filter survival at 30% attackers 0.50/0.55/0.62; stealth survival 0.60/0.73/0.80 vs sign-flip 0.30/0.50/0.60 (seed 42 only); live replay: 14/14 blocked, 12/14 named correctly (MITM → Ransomware, OS Fingerprinting → DDoS_ICMP).
- Code: grouped splits in `fl_ids/data/pipeline.py`, config flag `DataConfig.group_by_flow`, configs in `configs/full/`, scripts in `scripts/reruns/`, tools in `tools/`.
- Documents: `PAPER_NOTES.md`, `README.md`, `docs/results.html` (section 7d), report PDF (71 pages), deck (28 slides), two explainers.
- Live site: https://aronnnn1.github.io/FL-IDS/ (source in `docs/`).

## 5. Known limits (state these in anything we publish)
- MITM is one connection (406 rows): it goes wholly to the server's calibration set and is scored only by the zero-day test and the live replay.
- Smarter-attacker, pruning and clip tests at full scale ran with **seed 42 only**.
- The Vulnerability-scanner capture is damaged in the release; only its first 265,827 readable packets were replayed (tolerant extraction, with a test).
- Weaker at full scale and **cause not established**: the autoencoder backstop (alone 0.457/0.492/0.221 vs 0.737/0.765/0.612 earlier), zero-day detection, trust filter.
- Figures, PDFs and slides were checked by page count and text only, **never by eye**.
- Not done: zero-day under the stealth attacker or for pruned models; inline/streaming mitigation; a second dataset; a split by capture file; the guide's checklist (never received).
- `configs/config_vmware_check.yaml` is generated and deliberately not committed.

## 6. Parked task: seed repeats (needs the owner's choice first)
Run seeds 43 and 44 at full scale for the tests that only have seed 42.
- **Option A: stealth attacker only** (about 3 h of VM compute). Recommended: its claim (the smarter attacker is not harder to resist) is surprising and needs repeats.
- **Option B: stealth + pruning + clip** (about 8 h).
- **Option C: none**: label them "single run" in the paper (already stated in the notes).
The owner has **not chosen**. Ask before running anything.
If chosen: use `scripts/reruns/run_attack_phase_a.sh`, `tools/run_sharded_seeds.py` (atomic `.claim` dirs, `.done` markers; release stale `.claim` dirs after a crash), configs under `configs/full/`, in-process workers only, then rebuild with `tools/summarize_full.py` / `tools/build_full_tables.py` / `deliverables/scripts/full_figures.py`, add a section to `PAPER_NOTES.md` and `docs/results.html`, run the tests (`venv/bin/python -m pytest`), commit and push.

## 7. Other open items, in suggested order
1. **Website for presenting all findings** (the owner's next topic; the existing site is the starting point). Ask: replace, extend or separate site; audience (guide/reviewers/wider).
2. Look at the figures, report, deck and explainers by eye (render pages to images inside the VM).
3. Investigate why the trust filter and autoencoder backstop weaken at scale.
4. Seed repeats (section 6).

## 8. How to get started
```bash
ssh fl-ids-vm
cd ~/FL-IDS-clean && git pull && git log --oneline | head -3   # expect afd23e0 then the commit adding this file
venv/bin/python -m pytest -q                                   # about 9 minutes; 244 passed, 1 skipped
```
The deck/report tools live in `~/tools-venv` (python-pptx) and texlive/xelatex, WeasyPrint, LibreOffice are installed. GitHub login in the VM is the owner's account (Aronnnn1); never print or copy the token.
