# PAPER_NOTES — raw material for the FL-IDS paper

> **Maintenance rule (applies every session):** this file is updated at the
> end of every phase, in the same commit as that phase's code, and pushed to
> `origin` at once so the remote never falls behind. Update it whenever a
> run produces numbers, a design changes, or a limitation turns up.
>
> **Number rule:** every number here was produced by an actual run and is
> tagged with its source (commit, script or log, seed, rounds). Never add
> estimated, rounded-for-effect or not-yet-produced numbers; write
> "pending" instead. Superseded numbers move to §9 ("Do not cite") with the
> reason, and are never silently deleted.
>
> This is notes, not prose. The paper gets written from this.

Last updated: 2026-11-02 -- §8.15: the whole federated system on all 1.99M rows, split by connection (the headline federated results now). Earlier: 2026-11-01 (later) -- §8.14: seeds 43/44 of the sweeps, adaptive attacker, pruning, time-ordered split. Earlier: real 20-client run, seeds 43/44 and the VMware re-host are in §8.13.
Previous: 2026-10-16 -- **project complete.** Every phase is done
(§0), the code and results are committed and pushed (`a06711e`,
`4e19944`), and the full test suite passes (233 passed, 2 skipped). The
service-port/content/flow features (§8.10) are integrated into the
federated pipeline and Phase B, and every federated experiment was re-run
with them (§8.11). How much data each part trains on: §5.5 (read it
before writing any "trained on N packets" sentence). What remains is the
paper itself; open items are limitations / future work (§10, §12).
Previous update: 2026-09-27, on a new machine (MacBook Pro M5, UTM Ubuntu
26.04 VM; see setup notes below). Not yet committed to git as of this
update -- numbers below are tagged "this session" rather than a commit
hash where that's the case; update with the real commit hash once
committed. Phase 6 now fully complete (ablation, poisoning sweep, and the
standalone zero-day experiment all done -- §8.3, §8.5). Phase 11's
real-data Phase A completed end-to-end for the first time (§8.1a) --
resolves the old VM's OOM handoff note, §12.1. Phase 7 re-run against
that real bundle, correcting the pre-fix demo's misclassification (§8.7).
New: a supervised DL classifier built and compared against boosting
head-to-head, a comparison CLAUDE.md's spec didn't call for but the
project owner asked for directly (§8.9).

**Environment note**: this machine's UTM VM only has 7.2GB RAM by default
(bumped to 12GB temporarily for the real multi-process Phase A run, then
reverted). The real Phase A run (1 server + 10 client OS processes) came
close to OOM purely from per-process library-import overhead (torch/
lightgbm/flwr/pandas x11), not from training data size -- fixed by
setting `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1` before launching, which
cut swap usage from 1.7GB to under 900MB. Worth carrying forward as a
standard launch prefix for any future real multi-process run.

---

## 0. Status by phase (from git log, not assumed)

| Phase | Milestone commit | State |
|---|---|---|
| 0 Scaffolding | `3d0b5d9` | done |
| 1 Data pipeline | `494cb4d` | done; later fixes `c1cc656` (label leak), `6bea978` (MITM repair), `6bb8317` (z-score clip) |
| 2 Boosting bootstrap | `b097c83` | done; later `2009d90` (leaf regularization), `54d8d18` (incremental update) |
| 3 Core FL loop | `af49e8f` | done |
| 4 Robustness layer | `a47d93f` | done; exclusion rule changed in `7d127a0` (§4.6) |
| 5 Real data | `680e1a7` | done; its numbers predate the leak fix (§9) |
| 6 Evaluation | `854cd3b` harness; `0224a6d`, `2341ed8`, `11103fe` | **fully complete** (this session, 2026-09-26): ablation (§8.2), poisoning sweep (§8.3), and standalone zero-day (§8.5) all done, 20 rounds, seed 42 |
| 7 SDN | `5cbb35c`; re-run this session (2026-09-27) | **done with a real Phase A bundle** (§8.7) -- corrected the pre-fix demo's misclassification |
| 8 Dashboard | `0fa7c81`; app tests `f48f5fe`; bug found+fixed this session | **done, now actually verified live** (Training view watched in a real browser during a real Phase A run this session -- round 20, 10/10 clients surviving, boosting model v7, all per-client panels populated with real data) |
| 11 Orchestration | `0a0726f`; real run this session (2026-09-27) | **real-data Phase A completed end-to-end for the first time** (§8.1a) |
| 9 End-to-end run | 2026-09-27; repeated with 130 features 2026-10-16 (`a06711e`) | **done**: Phase A -> Phase B back-to-back with the real bundle, no manual patching between them (§8.1a, §8.7, §8.11). The dashboard's Training view was watched live during a real run (§8.8); its Live Simulation view was not watched in a browser; on 2026-11-01 it was rendered headlessly (Streamlit AppTest) against the real bridge while Phase B held, and showed the live classification, the drop rule and the port table with no errors (`logs/audit/live_view_check.log`, §12.2) |
| 10 Polish | README `2dcad51`, `4e19944`; full pytest 233 passed, 2 skipped (2026-10-16, 7 min 32 s) | **done** |
| 12 Accuracy + integration | `11c1cfa` (classifier, §8.10), `a06711e` (federated + Phase B, §8.11), `4e19944` (site/notes) | **done**: 99.7% / 0.983 on held-out connections; all federated experiments re-run |
| 13 VMware re-host + real 20 clients | `e5453c7` (2026-11-01) | **done**: VM built by script, `pytest` 233 passed / 2 skipped there, real 1+20 process Phase A and Phase B, seeds 42-44 at 10 and 20 clients (§8.13) |
| 14 Follow-ups | 2026-11-01 (§8.14) | **done**: seeds 43/44 of ablation/sweep/zero-day, real attacker runs, adaptive attacker, weight pruning, clip comparison, time-ordered split, per-class breakdown of the 20-client dip |
| 15 Full pool | 2026-11-02 (§8.15) | **done**: whole federated system on 1.99M rows split by connection: 6 real runs, 77 in-process jobs, 14-capture Phase B |

---

## 1. Problem, motivation, framing (abstract/intro material)

- Problem: intrusion detection for IoT/IIoT traffic. Constraints: raw
  traffic shouldn't leave devices/sites (privacy, bandwidth); new attack
  types appear that a supervised classifier bounded by its label taxonomy
  can't name; federated training is exposed to poisoned client updates;
  detection is only useful if it drives enforcement.
- Five techniques, each covering a gap the others leave:
  1. **Boosting (LightGBM), first pass, supervised**: names known attack
     types cheaply and decisively.
  2. **Client-side autoencoder, second pass, unsupervised**: runs only on
     traffic boosting didn't confidently call an attack; flags
     reconstruction error above a per-client benign threshold as
     `anomalous` (zero-day signal). Trained only on boosting-filtered
     "normal" traffic.
  3. **Cosine-similarity trust filter**: server-side screening of client
     autoencoder weight deltas against poisoning.
  4. **Federated learning (Flower)**: trains the autoencoder across
     non-IID clients without moving raw traffic.
  5. **SDN (Mininet + Open vSwitch, OpenFlow 1.3)**: turns cascade
     classifications into flow-table actions (drop / meter rate-limit).
- Two-phase architecture (deliberate): Phase A = offline FL training
  producing evaluated models; Phase B = online mitigation demo loading
  them. This keeps ML correctness separate from distributed-networking
  problems, and the evaluation numbers come from Phase A.
- Contribution framing: an integration of all five, with measured
  per-stage and per-defense contributions (ablation), poisoning-fraction
  breakdown, zero-day (leave-one-class-out) detection, and live enforcement.
  Also a secondary contribution: data-quality findings on Edge-IIoTset
  (§5.3) that inflate results for any model trained on the authors'
  preprocessed CSV.

### Literature grounding (verbatim from CLAUDE.md; do not restate)

This isn't an untested architecture — each piece has real precedent in
peer-reviewed work from 2020 onward, and it's worth knowing which
papers back which decision, both for confidence going in and for the
related-work section of the writeup.

- **Federated autoencoder-based anomaly detection**: well-established.
  Mothukuri et al., "Federated-learning-based anomaly detection for
  IoT security attacks," *IEEE Internet of Things Journal*, 2021. Li et
  al., "DeepFed: Federated deep learning for intrusion detection in
  industrial cyber-physical systems," *IEEE Transactions on Industrial
  Informatics*, 2020. Hernandez-Ramos et al., "Intrusion Detection
  based on Federated Learning: a systematic review," *ACM Computing
  Surveys*, 2025 — the subfield is mature enough to be systematically
  reviewed, not a novel combination on its own.
- **Cosine-similarity trust filtering**: strongly established, and the
  literature also confirms the exact non-IID-vs-malicious confound this
  spec already flags as an open problem, not a bug. Zhu et al.,
  "Byzantine-robust Federated Learning via Cosine Similarity
  Aggregation," *Computer Networks*, 2024. Li et al.'s spatial-temporal
  analysis work (Byzantine-robust FL through spatial-temporal
  clustering, 2021) — essentially the published version of the
  round-to-round EMA trust score this spec requires. SignGuard (ICDCS
  2022) validates pairing cosine similarity with a magnitude/sign check
  specifically against sign-flipping attacks — the exact test attacker
  component 5 requires. A 2025 Byzantine-robust FL paper states plainly
  that gradient-similarity-based defenses degrade under highly non-IID
  data — the literature's version of the finding from the earlier
  prototype run.
- **Boosting for attack classification, and specifically a two-stage
  boosting+autoencoder cascade**: a 2023 paper in *Mathematical
  Biosciences and Engineering* proposes exactly this pairing — LightGBM
  for a first-pass decision, an autoencoder's reconstruction residual
  for a secondary decision on samples the first pass called normal.
  That's the direct precedent for the boosting-first ordering this spec
  now uses. On the federated-boosting side: Chen, Saad, and Poor,
  "Secure federated XGBoost learning for IoT intrusion detection,"
  *IEEE Transactions on Information Forensics and Security*, 2021;
  SecureBoost, *IEEE Intelligent Systems*, 2021 (the federated
  histogram-based approach this spec treats as a stretch goal).
- **FL + SDN mitigation**: El Houda, Hafid, and Khoukhi, "MiTFed: A
  Privacy Preserving Collaborative Network Attack Mitigation Framework
  Based on Federated Learning Using SDN and Blockchain," *IEEE
  Transactions on Network Science and Engineering*, 2023 — closest
  direct precedent for the FL-decides/SDN-enforces structure here.
  Edge-IIoTset itself (Ferrag et al., *IEEE Access*, 2022) is explicitly
  positioned by its authors for federated learning use, not just
  centralized training.

**On novelty**: a handful of searches turned up no single published
system combining all five of these specifically — federated
autoencoder, cosine-similarity trust filtering, a boosting-first
cascade, FL orchestration, and SDN mitigation, together. Every pair or
triple exists somewhere in the literature, but not the full five-way
combination. That's a reasonable basis to frame this as a genuine
integration contribution in the writeup — but it rests on a handful of
targeted searches, not a systematic review, so don't state novelty as
a settled fact in the paper without running a fuller, more exhaustive
literature search first to make sure nothing more recent or more
obscure already does this combination.

---

## 2. Related work (one line each)

From CLAUDE.md's literature grounding. Bibliographic details are as
CLAUDE.md gives them; verify each against the actual paper before citing.

| Work | Year / venue | What it establishes / how this project differs |
|---|---|---|
| Mothukuri et al., "Federated-learning-based anomaly detection for IoT security attacks" | 2021, IEEE Internet of Things Journal | Federated anomaly detection for IoT attacks. This project adds a supervised first stage, poisoning defense and SDN enforcement. |
| Li et al., "DeepFed: Federated deep learning for intrusion detection in industrial cyber-physical systems" | 2020, IEEE Trans. Industrial Informatics | Federated deep IDS for ICPS. No boosting cascade, no update-level Byzantine filtering, no SDN mitigation. |
| Hernandez-Ramos et al., "Intrusion Detection based on Federated Learning: a systematic review" | 2025, ACM Computing Surveys | FL-IDS is mature enough to be systematically reviewed; a federated autoencoder alone is not novel. |
| Zhu et al., "Byzantine-robust Federated Learning via Cosine Similarity Aggregation" | 2024, Computer Networks | Cosine-similarity aggregation defense. This project filters on deltas, adds a MAD relative threshold, norm clip, EMA trust and (from `7d127a0`) a sign check. |
| Li et al., Byzantine-robust FL through spatial-temporal clustering | 2021 | Round-to-round (temporal) trust, essentially the EMA trust score here. From `7d127a0` the EMA trust also gates exclusion. |
| SignGuard | 2022, ICDCS | Pairs cosine with a magnitude/sign check against sign-flipping, the exact test attacker used here. |
| (unnamed) Byzantine-robust FL paper | 2025 | Gradient-similarity defenses degrade under highly non-IID data. Matches the MAD-band widening measured in §4.6. **Needs a full citation before use.** |
| (unnamed) LightGBM + autoencoder-residual two-stage detector | 2023, Mathematical Biosciences and Engineering | Direct precedent for the boosting-first cascade ordering. **Needs a full citation.** |
| Chen, Saad, Poor, "Secure federated XGBoost learning for IoT intrusion detection" | 2021, IEEE TIFS | Federated boosting for IoT IDS. Here boosting is server-trained on a calibration set and broadcast, not federated. |
| SecureBoost | 2021, IEEE Intelligent Systems | Federated histogram boosting. A stretch goal in the spec; not implemented. |
| El Houda, Hafid, Khoukhi, "MiTFed" | 2023, IEEE Trans. Network Science and Engineering | Closest precedent for FL-decides / SDN-enforces. MiTFed uses blockchain; this project adds a cascade and a poisoning filter. |
| Ferrag et al., Edge-IIoTset | 2022, IEEE Access | The dataset, positioned by its authors for FL use. §5.3 lists preprocessing problems found in its released CSV. |

**Added during the build** (not in CLAUDE.md; the details below are from
memory, so verify them before citing):

| Work | Year / venue | Use here |
|---|---|---|
| Cao, Fang, Liu, Gong, "FLTrust: Byzantine-robust Federated Learning via Trust Bootstrapping" | 2021, NDSS | Precedent for giving updates with negative cosine to a reference direction zero weight (ReLU(cos)). Justifies the `opposes_consensus` check (§4.6). FLTrust uses a server-held root dataset for its reference; this project uses the coordinate-wise median delta. |
| Yin, Chen, Ramchandran, Bartlett, "Byzantine-Robust Distributed Learning: Towards Optimal Statistical Rates" | 2018, ICML | Coordinate-wise median and trimmed mean as robust aggregators, and their breakdown when the attacker fraction reaches the trim fraction or 50%. Relevant to the trimmed-mean-only ablation row and the 50% sweep point. |

**Novelty caveat (carry forward):** see the verbatim "On novelty" paragraph
above. A handful of targeted searches is not a systematic review. Run an
exhaustive search before claiming novelty in the paper.

---

## 3. System architecture as built

### 3.1 Components → modules
| # | Component | Module |
|---|---|---|
| 1 | Data pipeline | `fl_ids/data/pipeline.py`, `repair.py` |
| 2 | Boosting (bootstrap, broadcast, incremental update) | `fl_ids/models/boosting.py`, `boosting_update.py` |
| 3 | Autoencoder | `fl_ids/models/autoencoder.py` |
| — | Cascade decision rule (single shared implementation) | `fl_ids/models/cascade.py` |
| 4 | Flower client | `fl_ids/fl/client.py` |
| 5 | Trust filter | `fl_ids/robustness/trust_filter.py` |
| 6 | Trimmed-mean aggregation | `fl_ids/robustness/aggregation.py` |
| — | Sign-flip test attacker | `fl_ids/robustness/attackers.py` |
| 7 | Custom Strategy (`TrustFilteredStrategy`, subclasses FedAvg) | `fl_ids/fl/strategy.py` |
| 8 | Flower server (real multi-process) | `fl_ids/fl/server.py`, `launch.py` |
| 9 | SDN mitigation bridge (Flask REST) | `fl_ids/sdn/bridge.py` |
| 10 | OpenFlow 1.3 controller (os-ken) + Mininet topology | `fl_ids/sdn/controller.py`, `topology.py` |
| — | Live pcap → features (tshark), live inference | `fl_ids/sdn/feature_extraction.py`, `live_inference.py` |
| 11 | Phase A / Phase B entrypoints, model bundle | `fl_ids/orchestration/` |
| 12 | Evaluation harness | `fl_ids/eval/` |
| 13 | Streamlit dashboard | `fl_ids/dashboard/` |

### 3.2 Cascade decision rule (one definition, used by eval, dashboard, SDN)
- Boosting outputs a class and its probability. If the class is an attack
  and the probability is ≥ `cascade.confidence_threshold` (0.7), output
  that attack type with confidence = that probability. Stop.
- Otherwise the row goes to the autoencoder. If reconstruction error >
  the client's threshold, output `anomalous` with confidence =
  clip(error/threshold − 1, 0, 1). Otherwise output `benign`.
- Bug found and fixed in `854cd3b`: the threshold existed in two config
  fields, and only one was ever read. It now lives only in `cascade.*`.

### 3.3 Boosting stage
- Label source: **server-held calibration set** (5% of data, stratified).
  A design decision; the alternative, client-local labels, was not chosen.
- Cold start: trained before round 1. Clients never filter with an
  untrained model.
- Distribution: serialized LightGBM model bytes in each round's
  `configure_fit` config (`broadcast_every_n_rounds: 1`).
- Boosting always sees **raw** features. The autoencoder sees
  per-client-normalized features (§4.2).
- Incremental update (`54d8d18`): every 3 rounds, clients that survived
  the trust filter surface ≤50 autoencoder-flagged rows each, with
  analyst-confirmed labels (false alarms come back as Normal). The server
  continues training (+50 trees, LightGBM `init_model`) on calibration
  set + accumulated alerts. If the alerts contain a class the model has
  never seen, it **retrains**: continued training can't learn a new
  class, because its predicted probability is ~1e-14, its softmax
  hessian ~0, and `min_sum_hessian_in_leaf` blocks every split. In
  simulation a never-seen class went from 0% to 17% recognized after one
  update (`54d8d18` commit message).

### 3.4 Autoencoder
- Dense MLP, input 91 → 32 → 16 → **8** → 16 → 32 → 91, ReLU between
  layers, linear output. **7,299 parameters** (float32), computed from
  the architecture. Consistent with the harness's measured 583,920
  bytes/round = 10 clients × 2 directions × 7,299 × 4 B.
- MSE loss, Adam lr 1e-3, 5 local epochs, batch 64.
- Trains only on rows the current global boosting model passes (predicts
  Normal, or an attack below 0.7 confidence).
- Threshold = 97th percentile of reconstruction error on the client's
  held-out benign validation slice, recomputed every round.
- Returns a fixed-bin histogram of reconstruction error (50 bins over
  [0, 10]) with each update.

### 3.5 Trust filter + aggregation (as of `7d127a0`)
- Operates on **deltas** (client weights − the round's starting global
  weights), never raw weights.
- Reference direction = **coordinate-wise median** of the round's deltas.
- Per client: cosine similarity to the reference, and the L2 norm.
- **Excluded if any of three holds** (reason recorded per client per round):
  1. `mad_outlier`: similarity < median − 3·MAD (relative, per round).
  2. `opposes_consensus`: similarity < 0 (`min_cosine_similarity`).
  3. `low_trust`: EMA trust < 0.5 (`min_trust_score`). Trust =
     EMA(α=0.3) of (cos+1)/2, starting at 1.0.
- Survivors are norm-clipped to 2× the round's median norm, aggregated
  by **trimmed mean** (15% per side), and the result is added back onto
  the round's starting weights.
- If no client survives, aggregation is skipped for that round.

### 3.6 Test attacker (sign-flip)
- Trains honestly, then sends −5 × (true delta) (`amplification` 5.0).
- Reported example count: `max_client` (claims the largest client's
  count, `e5fd1c4`), so plain FedAvg faces the literature's
  count-inflating attacker. The trust filter and trimmed mean ignore
  counts.

### 3.7 Phase B path
- The Phase A bundle (`fl_ids/orchestration/artifacts.py`) is
  self-describing: boosting model, final global AE weights, each client's
  scaler (mean, scale) and threshold, the z-score clip, cascade settings,
  held-out metrics and provenance (seed, git commit, time). Phase B
  rebuilds everything from the manifest, never from the current config,
  and rejects an inconsistent bundle (thresholds recomputed from the
  saved weights must match the clients' final-round values).
- Mininet: one host per FL client (`h<i+1>` = client `i`, scored with
  that client's scaler and threshold) on one OVS switch; the controller
  is os-ken OpenFlow 1.3.
- Traffic = real Edge-IIoTset `.pcap` replayed with `tcpreplay` from a
  host. Features come from tshark with the authors' field list.
- Bridge: `{device_id, classification, confidence, stage}` → block
  (confidence ≥ 0.85, drop rule on `ipv4_src`), rate-limit (≥ 0.5,
  OpenFlow meter), else allow/monitor.
- Topology is source-agnostic: a switch port can bridge to a physical/VM
  NIC (not built yet).
- Root: Mininet runs under one sudoers rule for the argument-less
  `python3 topology.py`. Parameters travel through a fixed `/tmp` file.

---

## 4. Deviations from the spec (CLAUDE.md), and why

Reviewers will ask about these. Each has a commit.

1. **Controller built on os-ken, not provided** (`5cbb35c`). The spec
   expected an existing custom OpenFlow 1.3 controller and said not to
   default to Ryu. None was available, and the user asked for one to be
   built. It's built on os-ken, the maintained OpenStack fork of Ryu,
   not on abandoned Ryu. Its switch state (flow and meter stats, ports)
   is queried over OpenFlow multipart requests, so what the dashboard
   shows is what `ovs-ofctl dump-flows` shows.
2. **Boosting on raw features, autoencoder on per-client-normalized
   features** (`680e1a7`). The spec's per-client normalization, applied
   to boosting too, destroyed it: identical held-out rows scored ~0.94
   accuracy with raw features vs ~0.06 through a heavily skewed client's
   own scaler (leak-era measurement; the effect's size is what matters).
3. **Per-client z-scores clipped at ±10** (`6bb8317`). Not in the spec.
   Counter-like features (`udp.stream`, `tcp.seq`, `tcp.ack`) can barely
   vary inside one client's Dirichlet shard. In the DDoS_HTTP-holdout
   setup (seed 42), client 5's benign validation rows sat up to 1.41e4
   std out on `udp.stream` (train std 2.93). That client's mean
   reconstruction error was ~7,500 on 293 rows while every other
   client's was < 5, and the run's mean benign validation loss stayed
   at 405.6 → 400.6 over 20 rounds. With the clip it went 0.152 → 0.0146.
   Diagnostic script, not the harness; commit `6bb8317` message.
   Earlier "divergence" (final val loss 6.6e13 in a Backdoor-holdout
   run) was this effect, not unstable training: per-client delta norms
   stayed 0.3–9 throughout.
4. **Incremental boosting update source changed** (`54d8d18`). The spec
   says to update from "aggregated reconstruction-error histograms and
   any new labels surfaced from surviving clients". Histograms carry no
   features, so nothing trainable. Labels live only in the server's
   calibration set. Chosen with the user: surviving clients surface
   capped analyst-confirmed alerts. **This relaxes "raw traffic never
   leaves a client"** for ≤50 confirmed rows per client per update
   round. State it in the paper.
5. **Evaluation uses an in-process simulation** of the same client,
   attacker and aggregation code (`854cd3b`), because ~150 training runs
   per regeneration can't each afford real processes. The real
   multi-process path is exercised by the integration tests and Phase A.
6. **Trust filter exclusion rule extended** (`7d127a0`, decided with the
   user). The spec specifies a MAD relative threshold, and warns against
   fixed cosine cutoffs. Measured problem with MAD alone (20% sign-flip
   attackers, seed 42): honest similarities spread from ~0.15 (heavily
   skewed shards) to ~0.85, so MAD grew and the cutoff fell from +0.32
   (round 1) to as low as −0.78. Attackers at −0.02…−0.57 passed.
   Harness: malicious-client survival **0.775** at 20% (§8.4a). Added
   `opposes_consensus` (cos < 0: the sign boundary, FLTrust precedent,
   not a tuned value) and `low_trust` (EMA < 0.5, so history counts;
   before, the EMA was computed but gated nothing). Diagnostic after the
   change (12 rounds, seed 42, attackers {0,7}): attacker 7 excluded
   10/12 rounds, attacker 0 5/12 (~62% of attacker-rounds vs ~22%
   before). Honest clients excluded 9/96 client-rounds (vs 2/96).
7. **Convergence metric** (`11103fe`). "Rounds to convergence" = first
   round after which validation loss stays within 10% of the run's
   *total improvement* above its best (best + 0.1·(first − best)), and
   the run ends there; diverged runs report NaN. The earlier band,
   best × 1.1, reported NaN for a healthy run converging to ~0.015
   (±0.0015 is below round-to-round noise).
8. **Headline metrics are not accuracy** (`0224a6d`). About 71% of
   traffic is benign, so accuracy tracks benign FPR and *rises* when a
   poisoned autoencoder stops flagging anything. Headlines: attack
   macro-recall (each attack type weighted equally), benign FPR,
   detection F1, zero-day macro-recall, autoencoder-alone macro-recall.
   All variants are scored through one `flag_attacks` +
   `detection_metrics` path; boosting-only means "the cascade rule with
   no backstop", not bare argmax.
9. **Evaluation mirrors deployment normalization** (`0224a6d`). Each
   test row is scored with its own client's scaler and threshold. It
   used to go through client 0's scaler with a threshold pooled across
   clients.

---

## 5. Dataset and preprocessing (implementation details)

### 5.1 Source
- Edge-IIoTset, `DNN-EdgeIIoT-dataset.csv` (the authors' 61-feature
  selection), plus the per-device/per-attack `.pcap` captures for
  Phase B. 24 captures are present locally.
- Loaded 47 of 63 CSV columns (16 dropped per the authors' recipe:
  IDs/timestamps/payload, plus `Attack_label`, which is derivable from
  `Attack_type`).

### 5.2 After cleaning (current code, `6bea978` onward; log 2026-09-24 18:29)
- Rows: 2,219,216 loaded → **1,909,719** after cleaning (0 NaN rows,
  309,497 duplicates dropped).
- MITM repair: 1,214 dataset rows replaced by 1,229 re-extracted rows
  (before dedup).
- **Features after one-hot encoding: 91** (was 95 with the leak, 88
  after the placeholder fix, 91 after the MITM repair added real MITM
  DNS categories).
- 15 classes. Class distribution after cleaning (computed from the
  encoded labels, 2026-09-24):

| Class | Rows | % |
|---|---:|---:|
| Normal | 1,363,998 | 71.42 |
| DDoS_UDP | 121,567 | 6.37 |
| DDoS_ICMP | 67,939 | 3.56 |
| SQL_injection | 50,826 | 2.66 |
| DDoS_TCP | 50,062 | 2.62 |
| Vulnerability_scanner | 50,026 | 2.62 |
| Password | 49,933 | 2.61 |
| DDoS_HTTP | 48,544 | 2.54 |
| Uploading | 36,807 | 1.93 |
| Backdoor | 24,026 | 1.26 |
| Port_Scanning | 19,977 | 1.05 |
| XSS | 15,066 | 0.79 |
| Ransomware | 9,689 | 0.51 |
| Fingerprinting | 853 | 0.04 |
| MITM | 406 | 0.02 |
| **Total** | **1,909,719** | |

- Note: MITM and Fingerprinting are tiny after dedup. Their per-class
  metrics rest on very few test rows. Report supports next to them.

### 5.3 Data-quality findings in the released dataset (possible secondary contribution)
> **Prior report (found 2026-10-30):** the placeholder leak (item 1) was
> published first by M. M. Galal, "Provenance, Not Behaviour: A
> Serialisation Artifact in Edge-IIoTset ...", arXiv:2608.15761, 16 Aug
> 2026 (same "0" vs "0.0" mechanism, four leaking columns). Our fix
> (`c1cc656`, 24 Sep 2026) was independent but later: **cite Galal and do
> not claim the leak as new.** Galal keeps the MITM rows as released and
> does not report the column shift (item 2), uses random stratified and
> leave-one-device-out splits (no connection-grouped split), and adds no
> flow features, so items 2+ and section 8.10 stay ours. The website's
> Novelty section lists the closest prior work for every claim.
1. **Placeholder label leak** (`c1cc656`). The "field doesn't apply"
   placeholder is spelled `0` or `0.0` depending on the source capture,
   and the spelling follows the label. In `mqtt.topic`,
   `mqtt.conack.flags`, `mqtt.protoname` and `dns.qry.name.len`, every
   Normal row is `0` and every attack row `0.0`, with zero overlap in
   2.2M rows. After one-hot encoding, `mqtt.topic_0.0` alone separates
   benign from attack at **AUROC 1.0000**. After canonicalizing both to
   `0`, the strongest single feature is `tcp.flags.ack` at AUROC ~0.71;
   a test guards the maximum at < 0.9. Found because the zero-day
   experiment showed autoencoder-alone detection of exactly 100% for
   every held-out class. **Any published model trained on this CSV with
   the authors' recipe may be learning the file format.**
2. **Column-shifted MITM rows** (`6bea978`). In the authors' MITM
   capture CSV, values sit under the wrong column names. Row-aligned
   against our tshark extraction of the same pcap: their `tcp.seq` is
   really `udp.time_delta` (agreement 1.000), `udp.time_delta` is
   `dns.qry.type` (0.993), `dns.qry.qu` is `dns.retransmit_request_in`
   (0.993). 98.8% of those rows are in the DNN CSV, so a model learns an
   ARP-spoofing attack with no ARP fields. Repaired by re-extracting the
   authors' own pcap with the same fields. Afterwards, live-extracted
   MITM traffic matches training MITM rows 100%. Modbus (normal) has the
   same corruption, but none of its rows are in the DNN CSV, so it's
   simply out of distribution live.
3. **tshark version drift** (`33205b3`, `0949abf`). tshark 4.x prints
   booleans as True/False (the authors' output: 1/0) and hex as `0x00`
   (the authors': `0x00000000`). Unhandled, this silently zeroed
   `tcp.flags.ack` on every live packet. Share of our live Backdoor rows
   found among the authors' rows: 6.6% before, 0.998 after. Survey of
   captures after both fixes: 12 of 14 attack captures match at
   0.85–1.00, and MQTT normal devices at 0.967–0.999.

### 5.4 Splits and partition (config at `7d127a0`)
- Server calibration set: 5% of all rows, stratified. Boosting trains on
  it. Phase A holds back 20% of it (`calibration_eval_fraction`) to score
  each boosting version.
- Federated pool: the remainder, subsampled to **60,000 rows**
  (stratified) to bound runtime across ~150 evaluation runs.
- **10 clients**, Dirichlet label-skew partition **α = 0.3**, seed 42.
- Per client: 15% test slice, then 15% of the benign remainder as a
  benign validation slice (threshold calibration). The rest is training.
- Observed skew (seed 42): some clients get no benign validation rows,
  e.g. client 5 in Phase A (warning logged; threshold = ∞, so that
  client's autoencoder never flags). Client training sizes vary from
  ~800 to ~12,400 rows (diagnostic, pre-clip partition code, which is
  unchanged by the clip).
- Pending: exact per-client × per-class count table for seed 42, to
  generate after the regeneration (memory-bound while it runs).

---

> **Update 2026-11-02 (§8.15):** the main federated results now use the whole pool: 1,885,587-1,885,744 rows across the clients (split by connection) and a
> 71,853-79,866-row server calibration set. The numbers below describe the earlier 60k-pool runs.

### 5.5 Data scale: how many rows each part trains on (2026-10-16)
All counts are for the 130-feature pipeline and were read from the run
artefacts named below. **Do not write "the system was trained on 1.9M
packets".** What is true:

| Part | Trains on | Evaluated on | Source |
|---|---:|---:|---|
| Data processing (cleaning, 39 new features, flow grouping) | all 2,219,216 rows -> 1,985,768 unique | -- | §8.10 |
| Final classifier, accuracy target (§8.10) | **1,429,825** (72%) + 158,870 early-stopping (8%) | **397,073** unseen rows (20%), whole connections held out | `experiments/accuracy/results/full_grouped_bal_s42.json` |
| Same classifier on the 5% calibration share only | 89,359 + 9,929 | the same 397,073 | `full_grouped_bal_tf0.05_s42.json` (99.7% / 0.979) |
| Federated: server bootstrap classifier | 79,430 (4.0%) | 19,858 held back | `runs/phase_a/calibration.npz` |
| Federated: client autoencoders (10 clients) | 45,474 training rows (pool of 60,000; per client 736-11,549) + 5,530 benign threshold rows | 8,996 client test rows | `runs/phase_a/client_*.npz` |

- Citable sentences: "uses the full Edge-IIoTset (2.2M packets, 1.99M
  unique after cleaning)"; "the classifier was trained on 1.43M packets
  and tested on 397k packets from connections it never saw".
- The federated system as a whole trains on ~125k rows (~6% of the
  data) because the pool is capped at 60k for runtime (§5.4, limitation 11).
  The 5%-only classifier row shows the bootstrap loses little from this
  (0.979 vs 0.983 macro F1 on the same test set); the autoencoder at full
  scale is untested.

---

## 6. Hyperparameters (configs/config.yaml at `7d127a0`) and why

| Parameter | Value | Why |
|---|---|---|
| seed | 42 | fixed everywhere; LightGBM also `deterministic=True`, `force_row_wise`, `num_threads=1` (multi-threaded histograms weren't bit-reproducible: one class's recall swung 0.0–0.88 across identical runs, `680e1a7`) |
| num_clients / α | 10 / 0.3 | spec: 8–10 clients, α ∈ [0.1, 0.5] |
| val_benign / test fraction | 0.15 / 0.15 | |
| normalized_clip | 10 | §4.3 |
| calibration_fraction | 0.05 | |
| LightGBM rounds / lr / leaves | 300 / 0.05 / 31 | with `min_sum_hessian_in_leaf=1`, `lambda_l2=1`: without leaf regularization training diverged (held-out logloss min ~0.18 at iteration ~16, then 7–14 by 300), making benign FPR swing 0.1%↔16% when 1% of calibration rows changed. 31/0.05 gave the best held-out logloss (0.041 vs 0.056 for 127/0.1) (`2009d90`) |
| cascade confidence threshold | 0.7 | spec default |
| AE hidden / bottleneck | [32, 16] / 8 | spec: bottleneck 8 |
| AE lr / epochs / batch | 1e-3 / 5 / 64 | |
| anomaly percentile | 97 | spec default; implies ~3% benign FPR on validation by construction |
| FL rounds | 20 | spec start value; also used for the Phase 6 regeneration |
| trim fraction | 0.15 | spec |
| norm clip multiplier | 2.0 | spec |
| MAD threshold | 3.0 | |
| trust EMA α | 0.3 | 30% new round, 70% history |
| min_cosine_similarity / min_trust_score | 0.0 / 0.5 | §4.6 |
| attacker amplification / claimed count | 5.0 / max_client | §3.6 |
| boosting update every / +trees / alert budget | 3 rounds / 50 / 50 per client | |
| SDN block / rate-limit confidence | 0.85 / 0.5 | spec (tuned in the earlier prototype) |
| pool_subsample_size | 60,000 | runtime |

---

## 7. Evaluation protocol

- Test set = concatenation of every client's own test slice; each row is
  scored with its client's scaler and threshold (deployment-faithful).
- Variants (`fl_ids/eval/variants.py`), same data, same seed:
  `full_pipeline` (trust filter + trimmed mean, boosting pre-filter,
  cascade), `plain_fedavg`, `trimmed_mean_only` (no cosine filter),
  `autoencoder_only` (no boosting pre-filter; detection = AE alone),
  `boosting_only` (cascade rule, no backstop, no FL).
- Ablation run at 30% sign-flip attackers (clients {0, 6, 9} at seed 42).
- Poisoning sweep: full pipeline at 0/20/30/40/50% attackers. Reports
  malicious-client survival rate = share of attacker-rounds in which an
  attacker passed the filter into aggregation.
- Zero-day (leave-one-attack-class-out): for each of the 14 attack
  classes, remove it from the calibration set **and** every client's
  data before partitioning (so it's absent even from scaler statistics).
  Train, then score up to 5,000 of its rows as unseen traffic, each
  assigned to a random client and scored with that client's scaler and
  threshold. Reported by stage: boosting-only detection (cascade rule),
  autoencoder alone, cascade, share added by the autoencoder, boosting's
  top misattributed label, AE reconstruction-error AUROC vs benign, and
  costs (benign FPR, known-attack recall). Done standalone at 0%
  attackers, and per variant/fraction inside the ablation and sweep
  (`zero_day_macro_recall`).
- Communication cost: bytes/round = Σ clients (down + up) of flattened
  float32 weights. The boosting broadcast is not counted (flag it when
  reporting).

---

## 8. Results

### 8.1 Bootstrap boosting (server calibration hold-out)
Source: `runs/phase_a/boosting_metrics.json`, Phase A run 2026-09-24
18:29, code at `6bea978` (post-leak-fix, post-MITM-repair; boosting is
unaffected by later commits, which touch only normalized features and
the trust filter). Scored on the 20% calibration hold-out (19,097 rows).

- Accuracy 0.9626, macro F1 0.8775, weighted F1 0.9597, benign FPR 0.00022.

| Class | F1 | Recall | Support |
|---|---:|---:|---:|
| Backdoor | 0.9744 | 0.9500 | 240 |
| DDoS_HTTP | 0.7268 | 0.6144 | 485 |
| DDoS_ICMP | 0.9993 | 1.0000 | 679 |
| DDoS_TCP | 0.9990 | 1.0000 | 501 |
| DDoS_UDP | 1.0000 | 1.0000 | 1216 |
| Fingerprinting | 0.8000 | 0.6667 | 9 |
| MITM | 0.6667 | 0.5000 | 4 |
| Normal | 0.9792 | 0.9998 | 13640 |
| Password | 0.8238 | 0.7214 | 499 |
| Port_Scanning | 0.8951 | 0.9600 | 200 |
| Ransomware | 0.9231 | 0.8660 | 97 |
| SQL_injection | 0.8263 | 0.7303 | 508 |
| Uploading | 0.7368 | 0.6087 | 368 |
| Vulnerability_scanner | 0.9631 | 0.9400 | 500 |
| XSS | 0.8487 | 0.7616 | 151 |

Observation: without the leak, the classes boosting struggles with
(DDoS_HTTP, Uploading, SQL_injection, Password, XSS) are the
application-layer attacks that look most like benign HTTP/MQTT traffic.
That is the traffic the autoencoder backstop exists for.

**Per-class precision and AUROC — done** (this session, new script
`fl_ids/eval/stage_report.py`, since none of the ablation/sweep/zero-day
scripts ever computed anything beyond recall — see `results/
per_class_stage_report.csv`, full pipeline trained fresh at 0% attackers,
20 rounds, seed 42):

| Class | Precision | Recall | F1 | AUROC | Support |
|---|---:|---:|---:|---:|---:|
| Backdoor | 0.990 | 0.928 | 0.958 | 0.9982 | 111 |
| DDoS_HTTP | 0.833 | 0.628 | 0.716 | 0.9880 | 223 |
| DDoS_ICMP | 1.000 | 1.000 | 1.000 | 1.0000 | 321 |
| DDoS_TCP | 1.000 | 1.000 | 1.000 | 1.0000 | 246 |
| DDoS_UDP | 1.000 | 1.000 | 1.000 | 1.0000 | 564 |
| Fingerprinting | 1.000 | 1.000 | 1.000 | 1.0000 | 3 |
| MITM | 1.000 | 1.000 | 1.000 | 1.0000 | 1 |
| Normal | 0.961 | 0.999 | 0.980 | 0.9944 | 6415 |
| Password | 0.957 | 0.759 | 0.847 | 0.9840 | 237 |
| Port_Scanning | 0.846 | 0.971 | 0.904 | 0.9992 | 102 |
| Ransomware | 0.944 | 0.850 | 0.895 | 0.9972 | 40 |
| SQL_injection | 0.956 | 0.706 | 0.812 | 0.9806 | 245 |
| Uploading | 0.931 | 0.572 | 0.709 | 0.9786 | 166 |
| Vulnerability_scanner | 0.992 | 0.942 | 0.966 | 0.9976 | 257 |
| XSS | 0.962 | 0.769 | 0.855 | 0.9843 | 65 |

Stage-level: boosting_alone accuracy 0.9629, macro F1 0.9095, weighted F1
0.9601, benign FPR 0.0006. Same run's autoencoder_alone (binary
benign/attack framing): accuracy 0.8328, macro F1 0.7611, AUROC 0.8049.
Cascade_combined: accuracy 0.9438, macro F1 0.9305. (MITM and
Fingerprinting supports are tiny here — 1 and 3 rows respectively, this
being a single test-slice draw, not the full dataset's held-out count;
read those two rows as anecdotal, not statistical, per §5.2's standing
caution on tiny classes.)

### 8.1a Real-data Phase A, real multi-process run — COMPLETE (first time)
Source: `runs/phase_a/` logs and `saved_models/phase_a/manifest.json`,
this session, 2026-09-27 13:22-13:27 (~5 minutes). A real Flower server
plus 10 real separate client OS processes (not the in-process simulation
used everywhere else in §8) -- the actual component-8 requirement
("real distributed run... against real separate client processes").
Previous attempts on the old machine never finished (interrupted at round
10/20, reason not recorded); this run went cleanly for the full 20 rounds
once the memory issue (see top-of-file environment note) was fixed.

- Bootstrap boosting (server calibration, 76,388 rows): accuracy 0.963 --
  consistent with §8.1's 0.9626 from the earlier run (same code path,
  different calibration split by chance of the train/test RNG state, but
  same order of magnitude as expected from a deterministic seed).
- Federated pool: 60,000 rows (subsampled per `pool_subsample_size`)
  across 10 clients, client 5 again got zero benign validation rows
  (same Dirichlet-skew behavior as §5.4 describes).
- **Final cascade result on the 10 clients' held-out test slices: attack
  macro-recall 0.889, benign FPR 0.0346** -- matches the in-process
  simulation's numbers closely (§8.2's full_pipeline: 0.8868/0.0260;
  §8.3's 0% point: 0.8837/0.0296). This is a real, useful cross-check:
  the in-process simulation (deviation #5, §4) is not just faster but
  actually representative of the real multi-process path's outcome.
- Bundle saved to `saved_models/phase_a/` (boosting model, AE weights,
  per-client scalers/thresholds, manifest) -- this is what Phase B (§8.7)
  loaded for its re-run.

### 8.2 Ablation (30% sign-flip attackers, 20 rounds, seed 42, commit `7d127a0`) — COMPLETE
Source: `results/ablation_table.csv`, `results/ablation_zero_day_detail.csv`
(written 2026-09-25 04:48), `results/ablation_per_class_recall.csv`
(2026-09-24 20:48). Attackers = clients {0, 6, 9}. Zero-day columns: each
variant retrained once per held-out attack class (14 × 5 runs), with 30%
attackers in every run.

Full table (exact CSV values):

| Variant | attack_macro_recall | attack_micro_recall | benign_fpr | detection_f1 | zero_day_macro_recall | autoencoder_alone_attack_macro_recall | final_val_loss | rounds_to_convergence | total_communication_bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_pipeline | 0.8868 | 0.8876 | 0.0260 | 0.9093 | 0.7308 | 0.4209 | 0.02121 | 3 | 11,678,400 |
| plain_fedavg | 0.8791 | 0.8834 | 0.0309 | 0.9014 | 0.5946 | 0.0000 | 9.199e+14 | NaN (diverged) | 11,678,400 |
| trimmed_mean_only | 0.8785 | 0.8822 | 0.0330 | 0.8982 | 0.5394 | 0.0000 | 4830 | NaN (diverged) | 11,678,400 |
| autoencoder_only | 0.1912 | 0.1337 | 0.0348 | 0.2191 | 0.3250 | 0.1912 | 0.02948 | 9 | 11,678,400 |
| boosting_only | 0.8750 | 0.8799 | 0.0000 | 0.9361 | 0.5178 | n/a | n/a | NaN (diverged) | 0 |

Zero-day detection rate by held-out class (cascade detection for
full_pipeline / plain_fedavg / trimmed_mean_only; AE alone for
autoencoder_only; cascade rule without backstop for boosting_only). Up to
5,000 held-out rows each (MITM 406, Fingerprinting 853 after dedup):

| Held-out class | full_pipeline | plain_fedavg | trimmed_mean_only | autoencoder_only | boosting_only |
|---|---:|---:|---:|---:|---:|
| Backdoor | 0.8060 | 0.7960 | 0.8038 | 0.0036 | 0.8570 |
| DDoS_HTTP | 0.3976 | 0.3244 | 0.3278 | 0.0562 | 0.3194 |
| DDoS_ICMP | 1.0000 | 1.0000 | 1.0000 | 0.8060 | 1.0000 |
| DDoS_TCP | 0.9750 | 0.9238 | 0.9180 | 0.1652 | 0.9026 |
| DDoS_UDP | 0.9028 | 0.9998 | 0.0922 | 0.8914 | 0.0922 |
| Fingerprinting | 0.8429 | 0.8300 | 0.9601 | 0.5064 | 0.8007 |
| MITM | 0.8867 | 0.0000 | 0.0000 | 0.8744 | 0.0000 |
| Password | 0.4228 | 0.3710 | 0.3732 | 0.1252 | 0.3420 |
| Port_Scanning | 0.9814 | 0.9212 | 0.9218 | 0.1310 | 0.9078 |
| Ransomware | 0.5358 | 0.5334 | 0.5332 | 0.0158 | 0.5298 |
| SQL_injection | 0.6144 | 0.5698 | 0.5672 | 0.0966 | 0.5256 |
| Uploading | 0.5128 | 0.4784 | 0.4780 | 0.0954 | 0.4264 |
| Vulnerability_scanner | 0.8346 | 0.1036 | 0.1004 | 0.6802 | 0.1026 |
| XSS | 0.5180 | 0.4734 | 0.4756 | 0.1022 | 0.4426 |

Readings:
- **Zero-day macro-recall: full pipeline 0.7308 vs boosting-only 0.5178**
  (+0.213), vs plain FedAvg 0.5946 and trimmed-mean-only 0.5394 (the same
  cascade with a poisoned AE). This is the backstop's contribution on
  attacks boosting never saw, and what poisoning takes away from it.
- Largest gains are where boosting has nothing to fall back on: MITM
  0.8867 (boosting-only 0.0000), Vulnerability_scanner 0.8346 (0.1026),
  DDoS_UDP 0.9028 (0.0922). Poisoned variants lose them (MITM 0.0000 for
  plain_fedavg and trimmed_mean_only; Vulnerability_scanner ~0.10).
- Anomalies to explain, not hide: (a) plain_fedavg gets DDoS_UDP 0.9998
  > full 0.9028 with a diverged AE (val loss 9.2e14): a blown-up AE still
  thresholds at the 97th benign percentile, so extreme-valued attacks
  clear it (this is what its 0.5946 macro-recall above boosting-only
  reflects). (b) trimmed_mean_only gets Fingerprinting 0.9601 > full
  0.8429. (c) Backdoor: boosting-only 0.857 > full 0.806. Candidate
  cause for (c): full_pipeline's boosting model is incrementally updated
  from alerts during training, boosting_only's is not. Unverified.
- Convergence: full_pipeline converges by round 3 (final val loss 0.0212).
  plain_fedavg (9.2e14) and trimmed_mean_only (4,830) diverge (NaN).
  autoencoder_only converges by round 9 (0.0295).
- Communication: 11,678,400 bytes over 20 rounds for every FL variant
  (= 583,920/round). Boosting broadcast excluded (§8.6).

Harness log lines for the main columns (same run, matching the CSV to 3 dp):

| Variant | Attack macro-recall | Benign FPR | AE-alone attack macro-recall |
|---|---:|---:|---:|
| full_pipeline | 0.887 | 0.0260 | 0.421 |
| plain_fedavg | 0.879 | 0.0309 | 0.000 |
| trimmed_mean_only | 0.878 | 0.0330 | 0.000 |
| autoencoder_only | 0.191 | 0.0348 | 0.191 |
| boosting_only | 0.875 | 0.0000 | n/a |

Readings:
- The trust filter is what keeps the federated AE usable under 30%
  attackers: AE-alone 0.421 vs 0.000 for both baselines.
- The boosting pre-filter roughly doubles AE-alone recall (0.421 vs 0.191).
- On *known* attacks the backstop adds little at the cascade level (0.887
  vs 0.875) and costs ~2.6% benign FPR. Its value has to come from the
  zero-day results.
- Cascade-level recall barely moves between variants because boosting
  (never FL-trained, so unaffected by poisoning) dominates. **Poisoning
  damage is only visible in the AE-alone and zero-day columns. Don't
  report cascade accuracy alone.**

Per-attack-type recall by variant (`results/ablation_per_class_recall.csv`,
written 20:48, same run):

| Attack type | full_pipeline | plain_fedavg | trimmed_mean_only | autoencoder_only | boosting_only |
|---|---:|---:|---:|---:|---:|
| Backdoor | 0.9640 | 0.9550 | 0.9550 | 0.0270 | 0.9459 |
| DDoS_HTTP | 0.6457 | 0.6413 | 0.6413 | 0.0135 | 0.6323 |
| DDoS_ICMP | 1.0000 | 0.9969 | 0.9969 | 0.3302 | 1.0000 |
| DDoS_TCP | 1.0000 | 1.0000 | 1.0000 | 0.1545 | 1.0000 |
| DDoS_UDP | 1.0000 | 1.0000 | 1.0000 | 0.1206 | 1.0000 |
| Fingerprinting | 1.0000 | 1.0000 | 1.0000 | 0.3333 | 1.0000 |
| MITM | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Password | 0.7511 | 0.7553 | 0.7468 | 0.1435 | 0.7511 |
| Port_Scanning | 0.9804 | 0.9216 | 0.9314 | 0.0294 | 0.9020 |
| Ransomware | 0.9250 | 0.9000 | 0.9000 | 0.0000 | 0.9000 |
| SQL_injection | 0.7469 | 0.7510 | 0.7429 | 0.0531 | 0.7429 |
| Uploading | 0.6566 | 0.6446 | 0.6386 | 0.0843 | 0.6386 |
| Vulnerability_scanner | 0.9611 | 0.9572 | 0.9611 | 0.1868 | 0.9533 |
| XSS | 0.7846 | 0.7846 | 0.7846 | 0.2000 | 0.7846 |

### 8.3 Poisoning-resistance sweep (full pipeline, 20 rounds, seed 42) — COMPLETE
Source: `results/poisoning_resistance_sweep.csv`, `results/poisoning_zero_day_detail.csv`
(written 2026-09-26 05:17, this session, on the new machine; run started
2026-09-26 00:11, ~5h wall clock but most of that was the VM suspended
overnight -- actual compute time much lower). Rerun of the run killed on
2026-09-25 (previous machine, OOM from a concurrent zero-day job); this
time run sequentially, per the memory-management lesson from that
failure. Now includes the previously-missing zero_day_macro_recall column.

| Malicious fraction | Attack macro-recall | Attack micro-recall | Benign FPR | Detection F1 | Zero-day macro-recall | AE-alone macro-recall | Malicious-client survival | Final val loss | Rounds to convergence |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.8837 | 0.8853 | 0.0296 | 0.9039 | 0.7358 | 0.4308 | n/a | 0.01374 | 3 |
| 0.20 | 0.8836 | 0.8861 | 0.0341 | 0.8992 | 0.7355 | 0.3737 | 0.275 | 0.00916 | 6 |
| 0.30 | 0.8868 | 0.8876 | 0.0260 | 0.9093 | 0.7308 | 0.4209 | 0.317 | 0.02121 | 3 |
| 0.40 | 0.8853 | 0.8876 | 0.0285 | 0.9064 | 0.7236 | 0.4133 | 0.238 | 0.02647 | 18 |
| 0.50 | 0.8777 | 0.8822 | 0.0340 | 0.8972 | 0.5943 | 0.0000 | 0.960 | 2.930e+17 | NaN (diverged) |

- Breakdown at 50%: the coordinate-wise median reference *becomes* the
  attackers' direction, so honest clients look like the outliers -- AE-alone
  collapses to 0.0000 and zero-day macro-recall drops from ~0.73 to 0.594.
  This is the expected limit of median-based defenses, now confirmed with
  the complete run (not just the harness log line).
- The 20% point's AE-alone (0.374) is still below the 30% point's (0.421)
  at seed 42. **Multi-seed check now done** (`results/multiseed_20_30_check.csv`,
  this session): seeds 43 and 44, same two points, `--skip-zero-day`
  (not needed for this specific metric):

  | Seed | 20% AE-alone | 30% AE-alone | 20% < 30%? |
  |---:|---:|---:|---|
  | 42 | 0.374 | 0.421 | yes |
  | 43 | 0.204 | 0.190 | **no** |
  | 44 | 0.334 | 0.337 | yes (barely) |

  **The ordering does not hold consistently — it flips at seed 43.**
  Conclusion: the 20%-vs-30% pattern is single-seed noise, not a real
  trend, and must not be claimed as one in the paper. Two further
  observations from the same table: (a) absolute AE-alone values vary a
  lot by seed even at the same fraction (0.19-0.42 range) — a reminder
  every single-seed number in this file carries real uncertainty the
  point estimate doesn't show; (b) `attack_macro_recall` stayed in a
  tighter, more stable 0.83-0.88 band across all 3 seeds x 2 fractions,
  so the cascade-level headline number is more seed-robust than the
  AE-alone diagnostic column, which is worth noting when deciding what to
  put weight on in the paper.
- Zero-day macro-recall stays close to the ablation's 30%-attacker value
  (0.7308, §8.2) across 0-40% malicious fraction (0.724-0.736), then drops
  sharply at 50% -- the backstop's zero-day value survives moderate
  poisoning and only fails where the whole trust filter fails.

### 8.4 Filter change, before vs after (same harness, 20 rounds, seed 42)
(a) MAD-only filter, commit `11103fe`. Points from the run that was
stopped once this problem was found (`results/logs` of that run, not
kept; values copied from its log lines at the time):

| Point | Attack macro-recall | Benign FPR | AE-alone | Survival |
|---|---:|---:|---:|---:|
| sweep 0% | 0.884 | 0.0296 | 0.431 | n/a |
| sweep 20% | 0.880 | 0.0323 | 0.397 | **0.775** |
| ablation full_pipeline (30%) | 0.883 | 0.0295 | 0.404 | — |
| ablation plain_fedavg (30%) | 0.879 | 0.0309 | 0.000 | — |
| ablation trimmed_mean_only (30%) | 0.878 | 0.0330 | 0.000 | — |

(b) New filter, `7d127a0`: §8.2 and §8.3. At 30%: AE-alone 0.404 →
0.421, benign FPR 0.0295 → 0.0260. At 20%: survival 0.775 → 0.275,
AE-alone 0.397 → 0.374 (worse). The trade-off is mixed on one seed;
report both sides.

### 8.5 Zero-day (leave-one-class-out) — COMPLETE
Per-variant zero-day at 30% attackers: complete, see §8.2. **Standalone
per-stage experiment (0% attackers) now complete too** (this session,
2026-09-26 06:19, `results/zero_day_holdout.csv`, `results/zero_day_holdout.png`).
All 14 attack classes, each held out of calibration set + every client's
data + scaler statistics, then scored as unseen traffic (up to 5,000 rows,
random client assignment).

| Held-out class | Boosting-only | AE-alone | Cascade | AE's added detection | Boosting's top misattribution | AE AUROC vs benign | Cascade benign FPR |
|---|---:|---:|---:|---:|---|---:|---:|
| Backdoor | 0.7912 | 0.2246 | 0.8552 | 0.0640 | Ransomware (72.7%) | 0.589 | 0.0363 |
| DDoS_HTTP | 0.3282 | 0.0506 | 0.3602 | 0.0320 | SQL_injection (19.4%) | 0.652 | 0.0320 |
| DDoS_ICMP | 1.0000 | 0.8038 | 1.0000 | 0.0000 | Fingerprinting (100%) | 1.000 | 0.0317 |
| DDoS_TCP | 0.9420 | 0.9898 | 0.9988 | 0.0568 | Port_Scanning (93.5%) | 0.994 | 0.0320 |
| DDoS_UDP | 0.0922 | 0.8914 | 0.9028 | 0.8106 | DDoS_ICMP (9.2%) | 0.999 | 0.0365 |
| Fingerprinting | 0.8101 | 0.6635 | 0.8300 | 0.0199 | DDoS_ICMP (68.0%) | 0.941 | 0.0318 |
| MITM | 0.0000 | 0.8941 | 0.8941 | 0.8941 | (none) | 0.998 | 0.0348 |
| Password | 0.3900 | 0.1352 | 0.4428 | 0.0528 | XSS (13.9%) | 0.701 | 0.0340 |
| Port_Scanning | 0.9300 | 0.8772 | 0.9924 | 0.0624 | DDoS_TCP (50.6%) | 0.979 | 0.0347 |
| Ransomware | 0.5332 | 0.0404 | 0.5372 | 0.0040 | Backdoor (43.0%) | 0.596 | 0.0294 |
| SQL_injection | 0.5780 | 0.1640 | 0.6138 | 0.0358 | Vulnerability_scanner (24.4%) | 0.616 | 0.0314 |
| Uploading | 0.4868 | 0.2278 | 0.5172 | 0.0304 | XSS (27.6%) | 0.672 | 0.0305 |
| Vulnerability_scanner | 0.1028 | 0.7660 | 0.8364 | 0.7336 | DDoS_HTTP (6.3%) | 0.936 | 0.0312 |
| XSS | 0.4708 | 0.1710 | 0.5206 | 0.0498 | DDoS_HTTP (24.4%) | 0.589 | 0.0309 |

Readings:
- **The three classes with zero (or near-zero) boosting-only detection --
  MITM (0.000), DDoS_UDP (0.092), Vulnerability_scanner (0.103) -- get
  the largest absolute lift from the backstop** (+0.894, +0.810, +0.734
  cascade detection respectively). These are exactly the classes boosting
  has no learned signal for at all, so the cascade's entire detection of
  them comes from the AE.
- Cascade is >= max(boosting-only, AE-alone) for every one of the 14
  classes -- the two stages are consistently complementary, never in
  conflict, on this data.
- Application-layer attacks (DDoS_HTTP 0.360, Password 0.443, XSS 0.521,
  Uploading 0.517) remain the hardest for both stages and the cascade
  combined -- consistent with §8.1's finding that these look most like
  benign HTTP/MQTT traffic.
- Boosting's misattribution pattern is informative: held-out classes
  mostly get mapped to their nearest behavioral neighbor (DDoS_ICMP -\>
  Fingerprinting, Port_Scanning -\> DDoS_TCP, MITM -\> nothing consistent
  at 0% since it's never predicted as a known attack at all).

### 8.6 Communication cost and convergence
- Per round: 583,920 bytes (10 clients × down + up × 7,299 float32
  parameters). Total over 20 rounds: 11,678,400 bytes per FL variant
  (ablation CSV, `7d127a0`).
- Rounds to convergence (ablation CSV): full_pipeline 3; autoencoder_only
  9; plain_fedavg and trimmed_mean_only diverged (NaN). Sweep values:
  pending.
- The boosting broadcast is not included (LightGBM text model; the
  bootstrap `boosting_model.txt` was 11,346,574 bytes on disk, so
  broadcasting it every round dwarfs the AE traffic). **Worth reporting;
  consider `broadcast_every_n_rounds` > 1 or broadcasting only on
  version change.**

### 8.7 SDN / Phase B
- **Re-run with a real Phase A bundle, this session (2026-09-27 13:31),
  corrects the earlier misclassification.** Source: `runs/phase_b/phase_b_result.json`.
  `Backdoor_attack.pcap` replayed via tcpreplay through Mininet/OVS (10
  hosts, one per FL client, os-ken OpenFlow 1.3 controller). 24,914
  packets, 23,895 classified non-benign. **Classification: Backdoor,
  confidence 0.997, boosting stage** (boosting alone was confident enough
  -- the AE backstop wasn't even consulted for this capture). Bridge
  action: block. Flow rule installed: `priority=100,ip,nw_src=10.0.0.1
  actions=drop`, verified present in the topology's captured
  `ovs-ofctl dump-flows` output, and the result's own consistency check
  (`check_mitigation`) passed.
- **This is the first time this capture has been correctly classified
  in a live Phase B run.** The original milestone demo (`5cbb35c`,
  pre-leak-fix models trained inside the demo, not a real Phase A bundle)
  classified the same pcap as DDoS_HTTP. That demo predates both the
  placeholder-label-leak fix and the tshark-drift fix (§5.3), and this
  result is direct on-live-traffic confirmation those fixes actually
  transfer to Phase B's tshark-extracted features -- not just to the
  held-out CSV test rows the rest of §8 evaluates on.
- **Mitigation latency, now measured -- and worth stating plainly, not
  glossing over**: the flow table's NORMAL-action entry shows 23,586
  packets already matched (5,983,953 bytes) *before* the block rule's own
  duration counter starts (0.002s at read time). That means the current
  architecture classifies only after tshark has extracted features from
  the **whole** replayed capture -- it is not an online, per-packet or
  streaming decision. For a replayed file, essentially the entire capture
  passes through as normal traffic before the block rule appears. This is
  a real architectural characteristic of the current Phase B pipeline
  (batch classification of a capture, not inline classification of a
  live stream), not a bug, and not yet reflected as a documented
  limitation before this update -- added to §10 below.

### 8.8 Dashboard live-verification and a real bug found this way
Source: this session, 2026-09-27. Watched `fl_ids/dashboard/app.py`
(Streamlit) in an actual browser (via the VM's network-exposed port)
during a real Phase A run, not just unit tests of the underlying data
functions.

- **Found and fixed a real bug the unit tests structurally couldn't
  catch**: the documented launch command, `streamlit run fl_ids/
  dashboard/app.py`, failed with `ModuleNotFoundError: No module named
  'fl_ids'`. Streamlit puts the *script's own directory*
  (`fl_ids/dashboard/`) on `sys.path`, not the repo root or the
  invoking shell's cwd, so the `from fl_ids... import ...` lines below
  it never resolved -- even with the venv active. The dashboard's own
  tests (`test_dashboard_app.py`, `test_dashboard_data.py`) import
  `fl_ids.dashboard.data` directly in-process, which never exercises
  this invocation path at all, so this had never been caught despite
  Phase 8 being marked "done" since `0fa7c81`. Fixed by inserting the
  repo root into `sys.path` at the top of `app.py` (mirrors the same
  fix `fl_ids/sdn/topology.py` already needed for its own root-invoked,
  non-`-m` launch path -- worth remembering as a pattern: any entrypoint
  launched by something other than `python -m fl_ids....` needs this
  explicitly, `-m` invocations get it for free). Verified fixed by
  re-running the exact documented command with no `PYTHONPATH`
  workaround and confirming it loads.
- **Training view confirmed genuinely live**, not just non-crashing:
  round counter at 20, "10/10" clients surviving the trust filter, mean
  benign reconstruction error 0.0129, a real declining reconstruction-
  error curve, boosting classifier panel showing model version 7 with
  "Model updated in rounds [4, 7, 10, 13, 16, 19]" (matches
  `update_every_n_rounds: 3`), per-client trust-score and
  reconstruction-error trajectories for all 10 clients, and the
  per-round filter-survival history -- every panel component 13's spec
  names is present and populated with this run's real data.
- **Not verified this session**: the Live Simulation (Phase B) view.
  §8.7's Phase B run was checked directly via its JSON result and the
  switch's own flow table, not through the dashboard's Phase B tab
  specifically (the run's hold window is short and wasn't timed against
  a dashboard session watching it). Worth doing once, for completeness,
  before calling component 13 fully closed on both views.

### 8.9 Boosting vs. supervised DL classifier (component-2 alternative, not in CLAUDE.md's spec)
Source: `results/classifier_comparison_summary.json`, `results/classifier_comparison_per_class.csv`,
this session, 2026-09-25/26. Not called for by CLAUDE.md -- added because
the project owner asked directly "would a DL classifier beat boosting for
the first-pass, supervised role component 2 plays." Distinct from
§8.2/§8.3's `autoencoder_only` variant, which tests the *unsupervised*
autoencoder as a standalone anomaly detector: this tests a genuinely
*supervised* DL classifier (dense MLP, same attack-type labels boosting
uses) head-to-head against LightGBM, both scored with the identical
per-class precision/recall/F1/AUROC path (`fl_ids.eval.metrics`).
New modules: `fl_ids/data/sampling.py` (capped stratified sampling, see
below), `fl_ids/models/dl_classifier.py`.

**Method**: both trained/evaluated on the same 500,000-row sample of the
full 1,909,671-row cleaned dataset, 400k train / 100k test (80/20,
stratified). The 500k sample uses **capped stratified sampling**, not
uniform random sampling or the project's usual Dirichlet partition: every
row of scarce classes is kept (MITM's 358 rows, Fingerprinting's 853, all
kept whole), and common classes are capped toward an even per-class
share via a water-filling allocation (largest class, Normal, capped from
1,363,998 down to 49,240 -- about 9.8% of the sample instead of 71%).
Deliberately not SMOTE/synthetic oversampling for the scarce classes --
this project has a documented history of synthetic-artifact bugs (the
placeholder leak, the column-shifted MITM rows, §5.3), and fabricating
flow-feature rows risked the same failure mode. Boosting sees raw
features as always (§3.3); the DL classifier sees the same rows
standardized with a `StandardScaler` fit on the training split only.

| | Boosting (LightGBM) | DL classifier (dense MLP) |
|---|---:|---:|
| Accuracy | 0.8908 | 0.6769 |
| Macro F1 | 0.8872 | 0.6214 |
| Weighted F1 | 0.8924 | 0.6685 |
| Benign FPR | 0.1599 | 0.5353 |
| Train time | 50.7s | 9.6s |
| Model size | 12,825,703 bytes (300 trees) | 8,271 parameters |

Per-class recall gap (boosting minus DL), largest first:

| Class | Boosting recall | DL recall | Gap |
|---|---:|---:|---:|
| XSS | 0.761 | 0.072 | +0.689 |
| Fingerprinting | 0.579 | 0.000 | +0.579 |
| SQL_injection | 0.767 | 0.213 | +0.554 |
| Port_Scanning | 0.997 | 0.499 | +0.498 |
| Uploading | 0.630 | 0.198 | +0.431 |
| Normal | 0.840 | 0.465 | +0.375 |
| DDoS_HTTP | 0.914 | 0.598 | +0.316 |
| Ransomware | 0.877 | 0.690 | +0.187 |
| Vulnerability_scanner | 0.957 | 0.820 | +0.137 |
| MITM | 1.000 | 0.903 | +0.097 |
| Backdoor | 0.928 | 0.905 | +0.022 |
| Password | 0.831 | 0.829 | +0.002 |
| DDoS_TCP / DDoS_UDP | 1.000 | 1.000 / 1.000 | 0.000 |
| DDoS_ICMP | 0.999 | 1.000 | -0.001 |

Readings:
- **Boosting wins decisively as a classifier**, not just as an anomaly
  detector -- macro F1 0.887 vs. 0.621. This is a second, independent
  line of evidence for the boosting-first design, complementary to
  §8.2/§8.3's autoencoder-alone result: not only is an *unsupervised*
  reconstruction-error detector a poor standalone substitute (0.19
  attack macro-recall there), a comparably-sized *supervised* DL
  classifier is also worse than boosting at the same task (0.62 macro F1
  here).
- The gap is largest on exactly the classes §8.1 already flagged as
  boosting's weak spot -- application-layer attacks that look most like
  benign traffic (XSS, SQL_injection, Uploading, DDoS_HTTP). Boosting's
  tree splits apparently generalize better on these than the MLP does
  with comparable training effort.
- On trivially-separable classes (DDoS_TCP/UDP/ICMP) both models hit
  ~100% -- the gap is entirely in the harder decision boundaries, not a
  blanket "boosting is better everywhere."
- **Caveat, stated plainly**: the MLP was small (8,271 parameters, 2
  hidden layers, 15 epochs) -- a deliberately modest, comparable-effort
  baseline, not an exhaustively tuned one. A larger or longer-trained DL
  classifier might close some of this gap; that was not tested. Don't
  overstate this as "DL cannot work here," only "this comparably-sized
  DL classifier does not."
- **Caveat**: both models' benign FPR (0.160, 0.535) is much higher than
  §8.1's leak-fixed boosting FPR (0.00022) -- expected, not a regression:
  this sample deliberately cuts Normal from 71% to ~10% of the training
  data, which shifts what "default" prediction the model settles on.
  Not comparable to §8.1/§8.2's FPR numbers, which use the natural
  class distribution.
- **Caveat**: this run used the MITM rows *without* the pcap-based repair
  (§5.3.2) -- the repair wasn't yet available when this comparison ran.
  MITM is a tiny class regardless (358-406 rows depending on dedup), so
  the effect on the headline macro-F1 numbers is negligible, but its own
  per-class recall (1.000 boosting / 0.903 DL) should be read with that
  caveat, consistent with §5.2's general tiny-class caution.

### 8.10 Classifier accuracy: service-port, content and flow features (2026-10-15)
Source: `experiments/accuracy/`: `build_features.py`,
`train_eval.py`, results JSON per run in `experiments/accuracy/results/`. Standalone
LightGBM on **all** cleaned rows (not the 60k pool, not the 500k sample), natural class
distribution, 80/20, early stopping on 10% of train. Params: 63 leaves, lr 0.1,
feature/bagging fraction 0.8, lambda_l2 1, min_sum_hessian 1. Target set by the
project owner: >=95% accuracy AND >=0.95 macro F1.

Why the base features stall: in SQL_injection/XSS/Uploading/Password only 5-17% of
packets carry any HTTP content (full_uri / payload); the rest are content-free TCP
handshake/ACK packets to port 80 on the same DVWA server. Ambiguity ceiling (oracle
giving each distinct feature vector its majority label), base 91 features: 2.31% of rows
ambiguous, ceiling accuracy 0.9875, ceiling macro recall 0.9692.

New feature groups (never IPs, absolute time, ephemeral ports or row order as features):
- `svc_port` (1): min(port < 32768) over tcp src/dst + udp port, else -1.
- `c_*` (18): decoded payload length/entropy/printable share, HTTP request flag, status
  code, header and X-header counts, URI length/params/%-count, file_data length,
  special chars, six generic keyword-group counts (sql, xss, upload, auth, trav, tool).
- `f_*` (20): per-flow aggregates; flow = (IP pair, proto, port pair) in capture order,
  new flow after 60 s idle OR 120 s active (CICFlowMeter's default active timeout).
  Without the active timeout one 264,094-packet VNC session (the only benign VNC in the
  dataset) was a single flow; under the grouped split it landed wholly in test and 16%
  of Normal test rows went to Backdoor/Ransomware (run superseded, not cited).
- Optional sqrt inverse-frequency class weights (`--balance`).

Dedup rows: base 1,909,719 (matches §5.2); +svc 1,909,980; full (130 features) 1,985,768.

| Features | Random acc | Random macro F1 | Flow-grouped acc | Flow-grouped macro F1 |
|---|---:|---:|---:|---:|
| base (91) | 0.9638 | 0.8868 | 0.9637 | 0.8892 |
| + svc_port (92) | 0.9802 | 0.9245 | 0.9803 | 0.9236 |
| + content (110) | 0.9802 | 0.9268 | 0.9802 | 0.9232 |
| + flow (130) | 0.9977 | 0.9879 | 0.9975 | 0.9808 |
| + class weights (final) | 0.9976 | 0.9867 | 0.9972 | 0.9828 |

Flow-grouped = StratifiedGroupKFold(5) first fold, groups = flow_id (no flow on both
sides). MITM is one ARP flow, so it has no test rows there and is excluded from that
split's macro F1; on the random split final MITM F1 = 0.994.

Seeds (final config): random acc 0.9976/0.9977/0.9976, macro F1 0.9867/0.9868/0.9866;
grouped acc 0.9972/0.9971/0.9970, macro F1 0.9828/0.9835/0.9851 (seeds 42/43/44).
Unweighted grouped macro F1 was seed-sensitive (0.9808/0.9560/0.9521) because
Fingerprinting (156 flows) swung 0.49-0.88 F1; weights fix it (~0.93).
Ceiling with all features: 0.01% ambiguous, 0.9999 / 0.9997.

Extra checks: (a) 500k capped sample, same training settings: base 0.8902 / 0.8827 ->
full 0.9919 / 0.9900. (b) Train on only 5% of rows (calibration-set size), grouped test:
base 0.9624 / 0.8807 -> full+weights 0.9968 / 0.9791.

Caveats: svc_port benefits from the testbed (benign = MQTT 1883 / VNC 5900, never HTTP);
flow features are whole-record (<=120 s), so this is flow-record classification, not
first-packet. Integrated into the federated pipeline and Phase B in `a06711e`;
federated results with these features are in §8.11 (§8.1-8.7 remain the
91-feature results, kept as the comparison).

Correction to §8.9: `results/classifier_comparison_summary.json` (current) gives DL
macro F1 0.6218 (not 0.6214), accuracy 0.6779, benign FPR 0.5341, boosting train 55.5 s;
DL SQL_injection recall 0.183 (not 0.213). Cite the JSON.

### 8.11 Federated pipeline with the extended features (2026-10-15/16) — COMPLETE
Code: `a06711e` (`fl_ids/data/features.py`; `data.extended_features: true`,
`data.feature_cache`, `boosting.class_weighting: "sqrt"`). Results:
`results/extended/` (same scripts, `--num-rounds 20`, seed 42, written to a
separate directory so §8.1-8.7's 91-feature results stay intact as the
comparison). Logs: `logs/extended/` on the VM. Everything else (10 clients,
Dirichlet 0.3, 60k pool, 5% calibration, trust filter, attacker) unchanged.
Numbers in brackets are the 91-feature results from §8.1-8.5.

**Integration checks.** The pipeline reproduces §8.10's dataset exactly:
2,219,216 rows -> 392,782 flows -> 1,985,768 rows x 130 features after
de-duplication. Phase B live extraction (all 61 tshark fields + the same
`derive_features`) on `Backdoor_attack.pcap`: 99.8% of the 24,914 live rows
are byte-identical to that capture's training rows across all 130 features
(base 99.8%, svc+content 99.9%, flow 99.9%). Tests: 233 passed, 2 skipped (224
before + 9 new in `tests/test_features.py`). The autoencoder is 130 -> 32 -> 16
-> 8 -> 16 -> 32 -> 130 = 9,834 parameters (was 7,299): 786,720 bytes/round,
15,734,400 over 20 rounds (was 11,678,400).

**Real Phase A** (1 Flower server + 10 client processes, 20 rounds, ~4 min,
`saved_models/phase_a/manifest.json`; the 91-feature bundle is kept in
`saved_models/phase_a_base91`): bootstrap boosting accuracy 0.997 (0.963), macro F1
0.985, trained on 79,430 calibration rows and scored on the 19,858 held
back (`runs/phase_a/calibration.npz`, `boosting_metrics.json`). On the clients' held-out slices: cascade attack
macro-recall **0.9986** (0.889), benign FPR 0.0350 (0.0346), detection F1
0.9556; boosting-only 0.9963 / FPR 0.0003 / detection F1 0.9984;
autoencoder-only 0.7414.

**Stage report** (`per_class_stage_report.csv`, 0% attackers): boosting alone
accuracy 0.9974, macro F1 0.9783, benign FPR 0.0002 (0.9629 / 0.9095 /
0.0006); autoencoder alone accuracy 0.9006, macro F1 0.8679, **AUROC 0.982
(0.805)**; cascade accuracy 0.9759, macro F1 0.9706 (0.9438 / 0.9305), benign
FPR 0.0332. Fingerprinting (3 test rows) boosting F1 0.857: anecdotal.

**Ablation, 30% sign-flip attackers** (`ablation_table.csv`):

| Variant | Attack MR | Benign FPR | Detection F1 | Zero-day MR | AE-alone MR | Final val loss | Rounds to conv. |
|---|---:|---:|---:|---:|---:|---:|---:|
| full_pipeline | 1.0000 (0.8868) | 0.0309 | 0.9612 | 0.9298 (0.7308) | 0.7120 (0.4209) | 0.0282 | 5.0 |
| plain_fedavg | 0.9977 (0.8791) | 0.0347 | 0.9554 | 0.7948 (0.5946) | 0.0019 (0.0000) | 4.987e+20 | NaN (diverged) |
| trimmed_mean_only | 0.9971 (0.8785) | 0.0334 | 0.9567 | 0.7986 (0.5394) | 0.0000 (0.0000) | 1.316e+04 | NaN (diverged) |
| autoencoder_only | 0.3723 (0.1912) | 0.0301 | 0.4646 | 0.5770 (0.3250) | 0.3723 (0.1912) | 0.0498 | 4.0 |
| boosting_only | 0.9962 (0.8750) | 0.0002 | 0.9982 | 0.7950 (0.5178) | n/a (n/a) | n/a | NaN (diverged) |

- The trust filter is still what keeps the AE usable: AE-alone 0.712 vs
  ~0 for plain FedAvg and trimmed-mean-only, whose losses diverge (4.99e20, 1.32e4).
- Zero-day: full pipeline **0.930** vs 0.795 boosting-only and ~0.80 for the
  poisoned variants (which fall back to boosting). The backstop adds ~0.13.
- **Trade-off to report:** on known attacks boosting-only now has the best
  detection F1 (0.998 vs 0.961): the AE's ~3% by-construction FPR costs more
  than the little it adds when boosting already catches ~99.6%. The cascade's
  value is zero-day detection, more clearly than in §8.2.

**Poisoning sweep** (`poisoning_resistance_sweep.csv`):

| Malicious | Attack MR | Benign FPR | Detection F1 | Zero-day MR | AE-alone MR | Attacker survival | Final val loss | Rounds to conv. |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.9997 | 0.0327 | 0.9588 | 0.9435 (0.7358) | 0.7366 (0.4308) | n/a (n/a) | 0.0308 | 4.0 |
| 0.20 | 0.9993 | 0.0318 | 0.9597 | 0.9388 (0.7355) | 0.7360 (0.3737) | 0.100 (0.275) | 0.0312 | 5.0 |
| 0.30 | 1.0000 | 0.0309 | 0.9612 | 0.9298 (0.7308) | 0.7120 (0.4209) | 0.117 (0.317) | 0.0282 | 5.0 |
| 0.40 | 0.9997 | 0.0332 | 0.9582 | 0.9011 (0.7236) | 0.6913 (0.4133) | 0.362 (0.237) | 0.0218 | 20.0 |
| 0.50 | 0.9974 | 0.0340 | 0.9561 | 0.8025 (0.5943) | 0.0000 (0.0000) | 1.000 (0.960) | 3.819e+18 | NaN (diverged) |

- Attack macro-recall 0.997-1.000 at every fraction; zero-day 0.901-0.943 up to 40%.
- Attacker survival fell at 20% / 30% (0.100 / 0.117, was 0.275 / 0.317) but
  **rose at 40% (0.362, was 0.238)**; the AE still held (0.691) and the
  loss stayed healthy (0.0218). Single seed: don't read a trend into it.
- 50%: the same documented breakdown (survival 1.000, AE-alone 0, loss 3.8e18);
  zero-day falls back to boosting (0.803).

**Multi-seed check** (`multiseed_20_30_check.csv`; seed 42 from the sweep):
attack macro-recall 0.996-0.999 for all seeds and both fractions; AE-alone
varies by seed, as before:

| Seed | Malicious | Attack MR | Benign FPR | AE-alone MR |
|---:|---:|---:|---:|---:|
| 43 | 20% | 0.9986 | 0.0312 | 0.738 |
| 43 | 30% | 0.9983 | 0.0311 | 0.734 |
| 44 | 20% | 0.9962 | 0.0328 | 0.623 |
| 44 | 30% | 0.9971 | 0.0319 | 0.565 |

**Zero-day, standalone** (`zero_day_holdout.csv`, 0% attackers): cascade
macro **0.943** (0.736), boosting-only 0.801 (0.533), AE-alone 0.757 (0.493),
benign FPR 0.032 (0.033). AE AUROC vs benign is 0.968-1.000 for every class
(was 0.59-0.70 for the HTTP family).

| Held-out class | Boosting-only | AE-alone | Cascade | Cascade (91 features) | Boosting's top misattribution | AE AUROC | Cascade FPR |
|---|---:|---:|---:|---:|---|---:|---:|
| Backdoor | 0.9934 | 0.4850 | 0.9970 | 0.8552 | Ransomware (99.3%) | 0.985 | 0.0374 |
| DDoS_HTTP | 0.6992 | 0.5786 | 0.8784 | 0.3602 | Vulnerability_scanner (28.8%) | 0.975 | 0.0306 |
| DDoS_ICMP | 1.0000 | 0.9052 | 1.0000 | 1.0000 | Fingerprinting (100.0%) | 1.000 | 0.0275 |
| DDoS_TCP | 0.9686 | 0.6906 | 0.9888 | 0.9988 | DDoS_HTTP (54.1%) | 0.988 | 0.0318 |
| DDoS_UDP | 0.7184 | 0.9488 | 0.9834 | 0.9028 | MITM (53.5%) | 0.998 | 0.0305 |
| Fingerprinting | 0.9931 | 0.7557 | 0.9989 | 0.8300 | DDoS_ICMP (66.6%) | 0.995 | 0.0310 |
| MITM | 0.0025 | 0.6946 | 0.6946 | 0.8941 | Port_Scanning (0.2%) | 1.000 | 0.0390 |
| Password | 0.8602 | 0.6930 | 0.9672 | 0.4428 | DDoS_HTTP (62.5%) | 0.994 | 0.0302 |
| Port_Scanning | 0.9888 | 0.8610 | 0.9992 | 0.9924 | Fingerprinting (98.8%) | 0.988 | 0.0338 |
| Ransomware | 0.9946 | 0.7694 | 0.9990 | 0.5372 | Backdoor (99.3%) | 0.994 | 0.0310 |
| SQL_injection | 0.9992 | 0.7848 | 0.9996 | 0.6138 | Vulnerability_scanner (99.9%) | 0.997 | 0.0341 |
| Uploading | 0.0796 | 0.7034 | 0.7156 | 0.5172 | Backdoor (5.8%) | 0.968 | 0.0364 |
| Vulnerability_scanner | 0.9584 | 0.9862 | 0.9966 | 0.8364 | SQL_injection (77.2%) | 0.999 | 0.0283 |
| XSS | 0.9596 | 0.7470 | 0.9902 | 0.5206 | Vulnerability_scanner (94.7%) | 0.983 | 0.0270 |

- **Regressions, report them:** MITM 0.894 -> 0.695 (its single ARP
  connection gets ordinary-looking flow features, so the AE finds it less
  unusual); Uploading boosting-only 0.487 -> 0.080 (unseen Uploading now
  looks Normal to boosting; the AE catches 0.703, and the cascade still goes
  0.517 -> 0.716); DDoS_TCP AE-alone 0.990 -> 0.691 (cascade 0.989).

**Phase B** (`runs/phase_b/phase_b_result.json`, new bundle): Backdoor,
confidence 0.997, boosting stage, **24,669 / 24,914** packets non-benign
(23,895 before), block, `priority=100,ip,nw_src=10.0.0.1 actions=drop`
verified in `ovs-ofctl dump-flows`. Still capture-level: 23,161 packets
matched the default NORMAL rule before the drop rule appeared. Running it
from this checkout needed a sudoers rule for its `topology.py` path and a
`venv` symlink (the topology script finds packages via `<repo>/venv`).

**Classifier-only note:** sqrt class weighting on the 91 base features alone
gives weighted F1 0.946 in `tests/test_boosting_real_data.py`, below its 0.95
bar; the test now uses the production (extended) feature set.

---

### 8.12 20 clients, the timed journey, class split (2026-10-30)
- **20 clients** (`configs/config_20clients.yaml`, in-process simulation via
  `fl_ids.eval.stage_report`, 20 rounds, seed 42, `results/clients20/`):
  classifier alone 0.9983 acc / 0.9952 macro F1; AE alone attack recall
  0.685, AUROC 0.977; cascade attack recall 0.9960, acc 0.9721, macro F1
  0.9662, benign FPR 0.0372 (10 clients: 0.728 / 0.982 / 0.9996 / 0.9759 /
  0.9706 / 0.0332). 3 of 20 clients (0, 2, 13) get no benign validation
  rows -> threshold inf, AE never flags. ~4.3 s/round. A **real**
  20-process run exhausted the VM's 7.4 GB RAM (swap full, round 1 took
  78 s) and was stopped: it needs more memory. (Done on a 24 GB VM: §8.13.)
- **Journey timing** (`fl_ids/utils/journey.py`; Phase A, Phase B and the
  live demo log each stage and keep `journey.json` current). One real run
  (`scripts/reruns/run_journey.sh`, 10 client processes, feature cache
  warm): Phase A 210.6 s (training 191.2 s; rounds with a boosting update
  are the slow ones), Phase B 8.6 s (tshark extraction 2.6 s, classify
  0.6 s, drop rule 0.007 s); total 219 s. Same results as 8.11 (0.999,
  FPR 0.0350; Backdoor 0.997, 24,669/24,914, block). `results/journey/`.
- **Class split** (`results/class_split/`): per class, raw / cleaned /
  classifier train-test / federated calibration / 20-client pool. The CSV
  has 2,219,201 rows; 2,219,216 after the MITM repair (1,214 -> 1,229).

### 8.13 Real 20-client run, seeds 43/44, VMware re-host (2026-11-01)
- **Environment.** The project was re-hosted on a VMware Workstation VM
  (Windows host; Ubuntu 26.04, Python 3.14.4, 12 vCPUs, 24 GB RAM), built by
  `D:\FL-IDS-VM\setup\setup_vm.py` (cloud image + `provision.sh`). Repo at
  `0d660bf` plus the new run scripts. `pytest` there: 233 passed, 2 skipped
  (`logs/vmware_check/pytest.log`). One fix on the way (`0d660bf`):
  `topology.py` hands `/tmp/fl_ids_live_demo_result.json` back to the sudo
  user, else a second Phase B run fails with `PermissionError`. All FL-IDS
  work runs inside this VM only (project owner's rule: attack data stays off
  the host).
- **Real 20-client run** (`configs/config_20clients_real.yaml` = `config_20clients.yaml`
  with outputs moved; `scripts/reruns/run_clients20_real.sh`; 1 Flower server
  + 20 client OS processes, 20 rounds, seed 42; `runs/clients20_real/`,
  `logs/clients20_real/`, bundle `saved_models/phase_a_20c_real`). It
  completed; the earlier real attempt on the 7.4 GB UTM VM did not (§8.12).
  Phase A 246.9 s (federated training 219.7 s); about 12 GB of the 24 GB in use
  at round 5 (one `free -g` sample, not a measured peak). Cascade attack
  macro-recall **0.978**, benign FPR **0.0362**, bootstrap boosting accuracy
  0.9969 / macro F1 0.9847. Phase B on that bundle (`Backdoor_attack.pcap`):
  Backdoor, confidence 0.997, boosting stage, 24,466 of 24,914 packets
  flagged, action *block*, rule `priority=100,ip,nw_src=10.0.0.1 actions=drop`
  read back from the switch; Phase B 9.0 s.
- **Seeds 43 and 44, 10 and 20 real client processes**
  (`scripts/reruns/run_multiseed.sh`, 20 rounds, no attackers; seed changes
  the data split, the Dirichlet partition and the initialisation; configs
  `configs/multiseed_*.yaml`, runs `runs/multiseed/`, logs `logs/multiseed/`).
  Table made by `tools/summarize_real_runs.py` (`results/real_runs/summary.{json,md}`);
  recall and FPR come from the "Phase A done" log line (recall to 3 decimals).
  The seed-42 10-client row is the VM re-check (`logs/vmware_check/`), which
  reproduces the §8.11 numbers (0.999 / 0.0350 there, 0.999 / 0.0340 here).

| Run | Clients | Total s | Training s | Attack macro-recall | Benign FPR | Boosting acc / macro F1 | Filter exclusions |
|---|---|---|---|---|---|---|---|
| 10 clients, seed 42 (VM re-check) | 10 | 341 | 226 | 0.999 | 0.0340 | 0.9969 / 0.9847 | 15 |
| 10 clients, seed 43 | 10 | 276 | 249 | 0.999 | 0.0311 | 0.9976 / 0.9847 | 2 |
| 10 clients, seed 44 | 10 | 262 | 234 | 0.996 | 0.0284 | 0.9968 / 0.9828 | 6 |
| 20 clients, seed 42 | 20 | 247 | 220 | 0.978 | 0.0362 | 0.9969 / 0.9847 | 38 |
| 20 clients, seed 43 | 20 | 238 | 211 | 0.999 | 0.0284 | 0.9976 / 0.9847 | 42 |
| 20 clients, seed 44 | 20 | 242 | 215 | 0.999 | 0.0396 | 0.9968 / 0.9828 | 27 |

- **Means over the three seeds.** 10 clients: attack macro-recall
  0.998, benign FPR 0.0312, Phase A 293 s. 20 clients: attack
  macro-recall 0.992, benign FPR 0.0347, Phase A 242 s. Only three
  seeds, so no confidence intervals are claimed.
- **What to say.** 20 real client processes match 10 on attack recall in two
  of three seeds (0.999 vs 0.999); seed 42 alone gives 0.978, which pulls the
  20-client mean down. We did not break that run down per class, so the cause
  is not established. Benign FPR stays 2.8-4.0% in every run.
- **Trust filter with no attackers.** With 0% malicious clients the filter
  still excluded clients in every run (client-rounds excluded over 20 rounds:
  10 clients 15 / 2 / 6 for seeds 42 / 43 / 44; 20 clients 38 / 42 / 27).
  These are honest clients whose non-IID updates look unlike the median, the
  confound already listed in §10 (non-IID vs. malicious). Exclusion is more
  frequent at 20 clients.
- **Not done.** Per-class results for the real 20-client run, and repeating
  the ablation, poisoning sweep and zero-day experiments with 20 clients or
  more seeds (hours each; §12).

### 8.14 Follow-up experiments: more seeds, real attackers, adaptive attacker, pruning, time-ordered split (2026-11-01)
Run in the VM, which was resized to 20 vCPUs / 48 GB for this (one training is single-threaded, so independent trainings run
side by side: `tools/run_sharded_seeds.py`, 40 jobs, 14 workers, all OK). Tables below are generated from the result files by
`tools/build_followups.py` (`results/followups/`); nothing is typed in. Seed-42 rows are the earlier runs (`results/extended/`).

**(a) Ablation, poisoning sweep and zero-day at seeds 43 and 44** (`results/seeds/s43`, `s44`, merged by
`tools/run_sharded_seeds.py`, summarised by `tools/summarize_seeds.py` into `results/seeds/summary.{md,json}`; 20 rounds).
Deviation: the per-held-out-class zero-day columns *inside* the ablation and sweep tables (about 85 extra trainings per seed)
were not repeated, so `zero_day_macro_recall` is empty there for seeds 43/44; the standalone zero-day experiment was repeated.

**Ablation at 30% sign-flip attackers, seeds 42 / 43 / 44 (source: results/seeds/summary.json)**

| Variant | Attack macro-recall | Autoencoder-alone recall | Benign FPR |
|---|---|---|---|
| full_pipeline | 1.000 / 0.999 / 0.997 | 0.712 / 0.679 / 0.565 | 0.0309 / 0.0284 / 0.0320 |
| plain_fedavg | 0.998 / 0.997 / 0.994 | 0.002 / 0.000 / 0.000 | 0.0347 / 0.0317 / 0.0297 |
| trimmed_mean_only | 0.997 / 0.997 / 0.996 | 0.000 / 0.000 / 0.026 | 0.0334 / 0.0291 / 0.0337 |
| autoencoder_only | 0.372 / 0.295 / 0.306 | 0.372 / 0.295 / 0.306 | 0.0301 / 0.0281 / 0.0325 |
| boosting_only | 0.996 / 0.997 / 0.996 | n/a / n/a / n/a | 0.0002 / 0.0000 / 0.0005 |

**Poisoning sweep, seeds 42 / 43 / 44**

| Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival |
|---|---|---|---|
| 0% | 1.000 / 0.999 / 0.997 | 0.737 / 0.765 / 0.612 | n/a / n/a / n/a |
| 20% | 0.999 / 0.999 / 0.996 | 0.736 / 0.739 / 0.618 | 0.10 / 0.03 / 0.23 |
| 30% | 1.000 / 0.999 / 0.997 | 0.712 / 0.679 / 0.565 | 0.12 / 0.12 / 0.27 |
| 40% | 1.000 / 0.998 / 0.997 | 0.691 / 0.620 / 0.537 | 0.36 / 0.31 / 0.44 |
| 50% | 0.997 / 0.997 / 0.995 | 0.000 / 0.000 / 0.000 | 1.00 / 0.99 / 0.97 |

**Zero-day detection of the unseen class, mean over 14 classes, seeds 42 / 43 / 44**

| Stage | Mean detection rate |
|---|---|
| Classifier alone | 0.801 / 0.748 / 0.791 |
| Autoencoder alone | 0.757 / 0.775 / 0.747 |
| Cascade | 0.943 / 0.952 / 0.952 |
| Cascade, DDoS_HTTP | 0.878 / 0.846 / 0.948 |
| Cascade, MITM | 0.695 / 0.963 / 0.837 |
| Cascade, Uploading | 0.716 / 0.677 / 0.665 |

- **What holds across all three seeds.** Attack macro-recall of the full pipeline is 0.995-1.000 at every fraction up to 50%.
  Plain FedAvg and trimmed-mean-only wreck the autoencoder at 30% attackers (autoencoder-alone recall 0.000-0.026; validation loss
  1.97e14 to 3.75e23 for FedAvg). The filter fails at 50% (attacker survival 0.97-1.00). Cascade zero-day detection averages
  0.943 / 0.952 / 0.952; classifier alone 0.801 / 0.748 / 0.791.
- **What moves with the seed.** Autoencoder-alone recall of the full pipeline at 30% ranges 0.565-0.712, and attacker survival at
  20% ranges 0.03-0.23: report ranges, not a single value. MITM zero-day detection ranges 0.695-0.963 (about 1,200 rows).
  Uploading is weak every time (0.665-0.716).
- Three seeds: no confidence intervals are claimed.

**(b) Where the real-run recall comes from** (`fl_ids.eval.bundle_report`; `results/real_runs/<run>/per_class_recall.csv`,
`per_client.csv`). The 20-client seed-42 dip (0.978) is one missed Fingerprinting test row out of 4 (0.25 / 14 classes = 0.018 of
macro-recall); micro recall is 0.9964. Clients with an infinite threshold (no benign validation rows) were still caught by
boosting. This explains the dip; it does not make small-class macro-recall stable.

**Where the real-run macro-recall comes from (source: results/real_runs/<run>/, made by fl_ids.eval.bundle_report)**

| Run | Macro-recall | Micro recall | Fingerprinting test rows, recall | MITM test rows, recall | Clients with infinite threshold |
|---|---|---|---|---|---|
| 10 clients, seed 42 | 0.999 | 0.9992 | 3 rows, 1.00 | 3 rows, 1.00 | 0 |
| 10 clients, seed 43 | 0.999 | 0.9992 | 4 rows, 1.00 | 4 rows, 1.00 | 1 |
| 10 clients, seed 44 | 0.996 | 0.9960 | 4 rows, 1.00 | 5 rows, 1.00 | 1 |
| 20 clients, seed 42 | 0.978 | 0.9964 | 4 rows, 0.75 | 1 rows, 1.00 | 3 |
| 20 clients, seed 43 | 0.999 | 0.9992 | 2 rows, 1.00 | 3 rows, 1.00 | 2 |
| 20 clients, seed 44 | 0.999 | 0.9988 | 2 rows, 1.00 | 3 rows, 1.00 | 2 |

**(c) Real multi-process Phase A with sign-flip attackers** (`scripts/reruns/run_attack_phase_a.sh`, `runs/attack_runs/`,
`logs/attack_runs/`): the trust filter excluded the attackers' updates in most client-rounds and no honest client.

**Real multi-process Phase A with sign-flip attackers (10 clients, 20 rounds, seed 42; source: runs/attack_runs/)**

| Attackers | Attacker clients | Attacker client-rounds excluded | Honest client-rounds excluded | Attack macro-recall | Benign FPR |
|---|---|---|---|---|---|
| 20% | 0,7 | 36 of 40 | 0 of 160 | 0.998 | 0.0335 |
| 30% | 0,6,9 | 52 of 60 | 0 of 140 | 0.999 | 0.0317 |

**(d) Adaptive attacker** (`fl_ids.robustness.attackers.StealthAttackerClient`, `fl_ids.eval.adaptive_attack`, in-process, seed 42).
White-box: it knows the filter's cosine rule and norm clip, estimates the consensus as the last aggregate update (this round's global
weights minus last round's), keeps cosine 0.1 to it, and puts the rest of its norm budget (1.5x its honest norm, under the 2x clip) on
the *negative* of its honest update's component orthogonal to the consensus. Round 1 it behaves honestly. It is one adaptive
strategy, not a proof for all. The sign-flip rows reproduce the main sweep (survival 0.10 / 0.12 / 0.36).

**Adaptive (stealth) attacker vs. sign-flip, seed 42, 20 rounds (source: results/adaptive/adaptive_attack.csv)**

| Attack | Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival | Final validation loss |
|---|---|---|---|---|---|
| sign_flip | 20% | 0.9993 | 0.730 | 0.10 | 0.026 |
| sign_flip | 30% | 1.0000 | 0.718 | 0.12 | 0.029 |
| sign_flip | 40% | 0.9997 | 0.663 | 0.36 | 0.021 |
| stealth | 20% | 0.9997 | 0.747 | 0.90 | 0.041 |
| stealth | 30% | 1.0000 | 0.741 | 0.72 | 0.040 |
| stealth | 40% | 0.9997 | 0.499 | 0.82 | 0.037 |

- The filter mostly **fails** against it (attacker survival 0.72-0.90 vs 0.10-0.36). Damage is bounded: known-attack recall stays
  >= 0.9997 (boosting), the trimmed mean and norm clip hold validation loss to about 1.5x the sign-flip value at 20-30%, and
  autoencoder-alone recall is unchanged at 20-30% but falls to 0.499 at 40% (sign-flip: 0.663). Zero-day detection under this
  attacker was **not** measured. Single seed.

**(e) Weight pruning (Objective 3)** (`fl_ids.eval.pruning`, `fl_ids.eval.pruning_fl`; `prune_weight_matrices` in
`fl_ids.eval.simulation`). Global magnitude pruning of the weight matrices (biases kept). Sizes are computed from non-zero counts
(float32 values plus int32 indices for a sparse layout): they are the size a sparse encoding would have, not a transmitted size.
Clients still train and send dense updates, so this implementation shrinks the model, not the per-round communication.

**Post-training magnitude pruning of the 10-client autoencoder, thresholds recalibrated (source: results/pruning/c10_s42/pruning.csv)**

| Sparsity | Non-zero weights | Sparse / dense bytes | Autoencoder recall | Autoencoder AUROC | Cascade macro-recall | Benign FPR |
|---|---|---|---|---|---|---|
| 0% | 9600 | 1.98 | 0.742 | 0.987 | 0.999 | 0.0340 |
| 50% | 4800 | 1.00 | 0.273 | 0.742 | 0.998 | 0.0287 |
| 70% | 2880 | 0.61 | 0.168 | 0.596 | 0.998 | 0.0292 |
| 80% | 1920 | 0.41 | 0.145 | 0.559 | 0.996 | 0.0334 |
| 90% | 960 | 0.22 | 0.144 | 0.594 | 0.996 | 0.0323 |
| 95% | 480 | 0.12 | 0.147 | 0.593 | 0.996 | 0.0366 |
| 98% | 192 | 0.06 | 0.147 | 0.593 | 0.996 | 0.0366 |

**Pruning during federated training (server re-prunes each round, linear ramp over the first 10 rounds), seed 42, no attackers (source: results/pruning/pruning_during_fl.csv)**

| Sparsity | Non-zero weights | Sparse / dense bytes | Autoencoder-alone recall | Cascade macro-recall | Benign FPR | Final validation loss |
|---|---|---|---|---|---|---|
| 0% | 9600 | 1.98 | 0.744 | 1.000 | 0.0320 | 0.034 |
| 50% | 4800 | 1.00 | 0.727 | 1.000 | 0.0323 | 0.040 |
| 70% | 2880 | 0.61 | 0.688 | 1.000 | 0.0298 | 0.049 |
| 80% | 1920 | 0.41 | 0.467 | 0.999 | 0.0312 | 0.080 |
| 90% | 960 | 0.22 | 0.176 | 0.998 | 0.0289 | 0.207 |

- Pruning *after* training hurts the backstop at once (autoencoder recall 0.742 -> 0.273 at 50%, AUROC 0.987 -> 0.742), though
  the cascade's known-attack recall stays >= 0.996 because boosting carries it. Pruning *during* training lets the model learn around
  the zeros: autoencoder-alone recall 0.744 -> 0.727 (50%) -> 0.688 (70%), then 0.467 (80%) and 0.176 (90%). At 70% the sparse
  layout is 0.61 of the dense bytes. Single seed, no attackers; zero-day detection of pruned models not measured.
- Not "free": the 9,834-parameter autoencoder is already tiny, and the saving only appears past 50% sparsity.

**(f) Per-client z-score clip** (`fl_ids.eval.clip_comparison`): benign validation loss with the clip 0.2047 at round 1 and 0.03369 at
round 20; without it 50.63 and 49.86 (about 1,500x worse and not converging). Single seed.

**Benign validation loss with and without the per-client z-score clip (source: results/clip/clip_comparison.csv)**

| Normalisation | Round 1 | Round 5 | Round 10 | Round 20 |
|---|---|---|---|---|
| clip 10 | 0.2047 | 0.04336 | 0.03999 | 0.03369 |
| no clip | 50.63 | 50.15 | 50 | 49.86 |

**(g) Time-ordered split** (`experiments/accuracy/train_eval.py --temporal`; `logs/temporal/`): each class's earliest ~80% of
connections train, its latest ~20% test (CSV row order is capture order within a class: time is non-decreasing in row order for every
class). Train 1,429,262 / test 397,699 rows, seeds 42-44. Accuracy 0.994 (grouped: 0.997). The drop in macro F1 (0.913 vs 0.983) is mostly
an artifact: MITM is a single connection, so it lands wholly in the test side, gets recall 0 and enters the mean; the grouped
split cannot score MITM at all. Removing MITM's zero from the mean gives about 0.978 (0.9133 x 15/14). Real losses: Backdoor 0.989 -> 0.947-0.962 and
DDoS_HTTP 0.980 -> 0.912-0.925. Caveat: time-of-day in the CSV carries no date, so this orders by row position, not by a verified clock.

**Per-class time-ordered split vs. connection-grouped split (source: experiments/accuracy/results/full_temporal_bal_s*.json)**

| Split | Accuracy | Macro F1 |
|---|---|---|
| Time-ordered, seeds 42 / 43 / 44 | 0.9942 / 0.9943 / 0.9941 | 0.9133 / 0.9122 / 0.9129 |
| Connection-grouped, seed 42 | 0.9972 | 0.9828 |

**Recall per class, time-ordered split (seeds 42 / 43 / 44) vs. grouped split (seed 42)**

| Class | Test rows (time-ordered) | Time-ordered recall | Grouped recall |
|---|---|---|---|
| Backdoor | 4835 | 0.947 / 0.948 / 0.962 | 0.989 |
| DDoS_HTTP | 9954 | 0.918 / 0.925 / 0.912 | 0.980 |
| DDoS_ICMP | 13752 | 1.000 / 1.000 / 1.000 | 1.000 |
| DDoS_TCP | 10013 | 1.000 / 1.000 / 1.000 | 1.000 |
| DDoS_UDP | 24314 | 1.000 / 1.000 / 1.000 | 1.000 |
| Fingerprinting | 258 | 0.977 / 0.977 / 0.977 | 0.937 |
| MITM | 406 | 0.000 / 0.000 / 0.000 | 0.000 |
| Normal | 287325 | 0.999 / 0.999 / 0.998 | 0.999 |
| Password | 10007 | 0.977 / 0.973 / 0.978 | 0.958 |
| Port_Scanning | 4044 | 0.998 / 0.998 / 0.998 | 0.999 |
| Ransomware | 2074 | 0.954 / 0.951 / 0.949 | 0.950 |
| SQL_injection | 10203 | 1.000 / 1.000 / 1.000 | 0.999 |
| Uploading | 7461 | 0.999 / 0.999 / 0.999 | 0.999 |
| Vulnerability_scanner | 10011 | 0.998 / 0.998 / 0.998 | 0.997 |
| XSS | 3042 | 0.983 / 0.984 / 0.984 | 0.986 |

**(h) Placeholder leak, measured** (`tools/leak_auroc.py`): before the fix the four affected raw columns separate attack from normal with
AUROC 0.9998-1.0. On the current 130-feature matrix (300,000-row sample) the best single feature is `f_rst` at 0.879, then `f_npkts` 0.866
and `svc_port` 0.835. The earlier "about 0.71" figure (the 91 base features, with a test capping it at 0.9) does not carry over to the
flow features, which reach 0.88; they are connection summaries, not label-spelling artifacts.

**Single-feature AUROC, attack vs. normal (source: results/leak/single_feature_auroc.json; after: 300,000-row sample)**

| Feature | AUROC | State |
|---|---|---|
| mqtt.topic == 0.0 | 1.0000 | raw, before the fix |
| mqtt.conack.flags == 0.0 | 1.0000 | raw, before the fix |
| mqtt.protoname == 0.0 | 1.0000 | raw, before the fix |
| dns.qry.name.len == 0.0 | 0.9998 | raw, before the fix |
| f_rst | 0.8789 | 130-feature matrix, after |
| f_npkts | 0.8657 | 130-feature matrix, after |
| svc_port | 0.8350 | 130-feature matrix, after |
| f_fin | 0.8039 | 130-feature matrix, after |
| f_pl_nonzero | 0.7328 | 130-feature matrix, after |
| f_syn | 0.7108 | 130-feature matrix, after |

**(i) Phase B on the seed bundles** (`scripts/reruns/run_multiseed_phase_b.sh`): all four ended in a verified drop rule.

**Phase B on the multi-seed bundles, Backdoor_attack.pcap, every run ends with a drop rule read back from the switch (source: logs/multiseed/status_phase_b.log)**

| Bundle | Class | Confidence | Packets flagged | Phase B time |
|---|---|---|---|---|
| 10 clients, seed 43 | Backdoor | 0.997 | 24244 / 24914 | 10.8 s |
| 10 clients, seed 44 | Backdoor | 0.998 | 24914 / 24914 | 8.3 s |
| 20 clients, seed 43 | Backdoor | 0.997 | 24848 / 24914 | 11.1 s |
| 20 clients, seed 44 | Backdoor | 0.997 | 24914 / 24914 | 9.1 s |

**(j) Tests.** New: stealth attacker (`tests/test_attackers.py`), pruning helpers (`tests/test_pruning.py`). Final full run:
236 passed, 2 skipped in 582.8 s (logs/audit/pytest_final.log); the earlier 233 plus three new tests.

**Still not done after this section:** inline/streaming mitigation (§10.16); zero-day detection under the adaptive attacker and of pruned
models; the zero-day columns inside the ablation/sweep tables at seeds 43/44; a second dataset; the team's guide checklist (never received).

### 8.15 Full pool, split by connection: the whole federated system on all 1.99M usable rows (2026-11-01/02)
**What changed (decision of the project owner, 2026-11-01: train and test the whole pipeline on all usable rows, split by connection).**
- *Data.* All 1,985,768 unique rows go through the federated system. The server keeps a labelled calibration set (79,866 / 72,803 /
  71,853 rows for seeds 42 / 43 / 44, about 5%; the number varies because whole connections are chosen) to bootstrap the classifier. The
  rest (1,885,587 / 1,885,744 / 1,885,673 rows) is split across 10 or 20 clients. Client test slices hold 283,090-295,566 rows (was ~9,000).
  The zero-day experiment scores *every* row of the held-out class (up to 121,567; was capped at 5,000).
- *Split by connection* (`data.group_by_flow`, `fl_ids.data.pipeline.grouped_*`, `server_pool_split`). Packets of one connection share their
  flow-level features, so a row-level split put near-identical siblings on both sides. Now a connection stays whole in the calibration set,
  in exactly one client, and in exactly one of that client's train / benign-validation / test slices (`tests/test_grouped_split.py`).
  `data.min_flows_per_class: 20`: a class with fewer connections cannot be split. Only **MITM** (406 rows, **one connection**) is affected:
  all of it goes to the server's calibration set, so the classifier learns it, and no MITM row is in any client pool or test slice. MITM is
  therefore scored only by the zero-day experiment (and Phase B). 24 connections (655 rows) carry two labels; they are split per label.
- *Speed.* Each client caches its boosting-filter result per broadcast model version (the model changes every third round), which
  makes a full-pool round about 21 s instead of ~100 s; results are identical (tests unchanged). `encoded_extended.npz` also
  stores the connection id of every row (cache version 2).
- *Runs.* Real multi-process Phase A (1 server + 10 or 20 client processes, 20 rounds), seeds 42 / 43 / 44, plus 77 in-process jobs
  (`tools/run_full_experiments.py`: sweep, ablation variants, zero-day per class, stealth attacker, pruning, no-clip), and Phase B on all 14
  captures. Configs: `configs/full/`; outputs `results/full/`, `logs/full/`, `runs/full/`, `saved_models/full/`. Tables below come from
  `tools/summarize_full.py` + `tools/build_full_tables.py`. The earlier 60k-pool, row-split results (§8.1-8.14) are kept as the comparison.
- *Run history (for the record).* At 17:35 on 2026-11-01 a 20-client run was started next to 7 in-process jobs and the VM ran out of memory;
  the kernel killed every process. Work was restarted in stages (real runs alone, then 9 in-process jobs at ~4.4 GB each). Also found: one
  test (`tests/test_boosting_real_data.py`) overwrote the shared feature cache with a no-MITM-repair build; it now uses its own cache file.
  Neither affected a reported number (every run logs the matrix shape it loaded: 1,985,768 x 130).

**Leak check first** (`configs/config_leakcheck.yaml`, 60k pool, split by connection, seed 42; `results/real_runs/leakcheck_c10_s42/`): known-attack
micro recall of the classifier alone 0.9962 against 0.9968 for the row-split run: **splitting by connection did not lower known-attack recall**, so the
earlier federated recall numbers were not inflated by sibling packets. Packet-level false alarms were 0.0443 against 0.0340.

**Real multi-process Phase A on the full pool (1.89M rows), split by connection, 20 rounds, no attackers**

| Run | Phase A s | Attack macro-recall | Attack micro recall | Classifier-only micro recall | Packet-level false alarms | Connection-level false alarms | Test rows | Clients with no benign validation rows |
|---|---|---|---|---|---|---|---|---|
| 10 clients, seed 42 | 1844 | 0.9958 | 0.9974 | 0.9970 | 0.1275 | 0.0034 | 288,416 | 1 |
| 10 clients, seed 43 | 1397 | 0.9947 | 0.9978 | 0.9971 | 0.0884 | 0.0074 | 283,090 | 0 |
| 10 clients, seed 44 | 1754 | 0.9939 | 0.9956 | 0.9954 | 0.0248 | 0.0039 | 288,366 | 2 |
| 20 clients, seed 42 | 1260 | 0.9981 | 0.9989 | 0.9981 | 0.0588 | 0.0104 | 283,427 | 3 |
| 20 clients, seed 43 | 1063 | 0.9970 | 0.9980 | 0.9974 | 0.1628 | 0.0076 | 292,222 | 2 |
| 20 clients, seed 44 | 1225 | 0.9972 | 0.9978 | 0.9972 | 0.1089 | 0.0081 | 295,566 | 0 |

**The same runs at the earlier scale and now (macro-recall includes only attack types present in the test slices)**

| Setting | Attack macro-recall | Attack micro recall | Classifier-only micro recall | Benign FPR (packets) |
|---|---|---|---|---|
| 10 clients, seed 42: 60k pool, split by row | 0.9990 | 0.9992 | 0.9968 | 0.0340 |
| 10 clients, seed 42: full pool, split by connection | 0.9958 | 0.9974 | 0.9970 | 0.1275 |
| 10 clients, seed 42: 60k pool, split by connection | 1.0000 | 1.0000 | 0.9962 | 0.0443 |
| 10 clients, seed 43: 60k pool, split by row | 0.9985 | 0.9992 | 0.9976 | 0.0311 |
| 10 clients, seed 43: full pool, split by connection | 0.9947 | 0.9978 | 0.9971 | 0.0884 |
| 10 clients, seed 44: 60k pool, split by row | 0.9962 | 0.9960 | 0.9939 | 0.0284 |
| 10 clients, seed 44: full pool, split by connection | 0.9939 | 0.9956 | 0.9954 | 0.0248 |
| 20 clients, seed 42: 60k pool, split by row | 0.9784 | 0.9964 | 0.9952 | 0.0362 |
| 20 clients, seed 42: full pool, split by connection | 0.9981 | 0.9989 | 0.9981 | 0.0588 |
| 20 clients, seed 43: 60k pool, split by row | 0.9993 | 0.9992 | 0.9980 | 0.0284 |
| 20 clients, seed 43: full pool, split by connection | 0.9970 | 0.9980 | 0.9974 | 0.1628 |
| 20 clients, seed 44: 60k pool, split by row | 0.9991 | 0.9988 | 0.9968 | 0.0396 |
| 20 clients, seed 44: full pool, split by connection | 0.9972 | 0.9978 | 0.9972 | 0.1089 |

**Reading the real runs.**
- **Known attacks are unchanged.** Micro recall 0.9956-0.9989, classifier alone 0.9954-0.9981 (earlier runs: 0.9939-0.9980). Macro-recall
  0.9939-0.9981 over the 13 attack types present in the test slices (MITM is absent by construction). The 20-client seed-42 dip (0.978) does not recur.
- **False alarms: two different numbers.** Packets flagged among normal test packets: 2.5%-16.3% (earlier: 2.8%-4.0%). But the *median
  client* is 2.9%-3.2% in all six runs, and counted per connection the rate is 0.34%-1.04% (`fl_ids.eval.flow_fpr`;
  `results/full/<run>/flow_fpr/`). The packet-level figure is dominated by a few very long normal connections (7,000-11,800 packets each,
  e.g. one flow of 11,764 packets flagged entirely): in five of six runs 80%-94% of the false-alarm packets come from the ten largest
  connections (52% in the sixth). Report both; do not quote 3% for the whole test set.
- **The autoencoder backstop is weaker at scale.** Autoencoder-alone attack recall with no attackers: 0.457 / 0.492 / 0.221 (earlier 0.737 / 0.765 /
  0.612). The cause is not established (candidates: a harder, connection-split benign threshold; larger, more homogeneous local data).
- **Phase A time** 1,063-1,844 s for 20 rounds (runs overlapped other jobs at times).

**Recall per attack type, 10 clients, seed 42, full pool, by stage (held-out test slices)**

| Class | Test rows | Classifier alone | Autoencoder alone | Cascade |
|---|---|---|---|---|
| Backdoor | 2263 | 0.9885 | 0.0367 | 0.9929 |
| DDoS_HTTP | 6915 | 0.9899 | 0.4807 | 0.9899 |
| DDoS_ICMP | 9520 | 1.0000 | 0.3171 | 1.0000 |
| DDoS_TCP | 6717 | 1.0000 | 0.9394 | 1.0000 |
| DDoS_UDP | 17755 | 0.9999 | 0.3063 | 1.0000 |
| Fingerprinting | 129 | 0.9845 | 0.0698 | 0.9922 |
| Password | 7795 | 0.9913 | 0.2517 | 0.9914 |
| Port_Scanning | 2929 | 1.0000 | 0.6842 | 1.0000 |
| Ransomware | 691 | 0.9841 | 0.4877 | 0.9870 |
| SQL_injection | 7228 | 0.9990 | 0.8944 | 0.9996 |
| Uploading | 5567 | 0.9998 | 0.5493 | 0.9998 |
| Vulnerability_scanner | 7216 | 0.9946 | 0.5006 | 0.9961 |
| XSS | 2274 | 0.9960 | 0.4714 | 0.9969 |

**Poisoning sweep, full pool**

| Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival |
|---|---|---|---|
| 0% | 0.996 / 0.996 / 0.994 | 0.457 / 0.492 / 0.221 | n/a / n/a / n/a |
| 20% | 0.995 / 0.996 / 0.994 | 0.466 / 0.483 / 0.258 | 0.30 / 0.40 / 0.23 |
| 30% | 0.995 / 0.997 / 0.995 | 0.490 / 0.373 / 0.245 | 0.50 / 0.55 / 0.62 |
| 40% | 0.994 / 0.994 / 0.992 | 0.297 / 0.139 / 0.074 | 0.60 / 0.64 / 0.61 |
| 50% | 0.995 / 0.990 / 0.985 | 0.249 / 0.000 / 0.000 | 0.64 / 1.00 / 0.99 |

**Ablation at 30% sign-flip attackers, full pool, seeds 42 / 43 / 44**

| Variant | Attack macro-recall | Autoencoder-alone recall | Benign FPR |
|---|---|---|---|
| full_pipeline | 0.995 / 0.997 / 0.995 | 0.490 / 0.373 / 0.245 | 0.1112 / 0.0653 / 0.0075 |
| autoencoder_only | 0.105 / 0.073 / 0.051 | 0.105 / 0.073 / 0.051 | 0.0473 / 0.0411 / 0.0445 |
| boosting_only | 0.990 / 0.989 / 0.982 | n/a / n/a / n/a | 0.0001 / 0.0001 / 0.0003 |
| plain_fedavg | 0.992 / 0.994 / 0.990 | 0.013 / 0.002 / 0.092 | 0.0947 / 0.0301 / 0.0301 |
| trimmed_mean_only | 0.995 / 0.995 / 0.993 | 0.205 / 0.000 / 0.025 | 0.1070 / 0.0261 / 0.0299 |

**Reading the sweep and ablation (full pool, three seeds).**
- Known-attack recall stays 0.985-0.997 at every fraction up to 50%.
- **The trust filter lets more attackers through at scale.** Attacker survival at 30%: 0.50 / 0.55 / 0.62 (earlier 0.12 / 0.12 / 0.27); at 50%: 0.64 / 1.00 / 0.99.
  Robust aggregation still protects the autoencoder: at 30% attackers the full pipeline's autoencoder-alone recall is 0.490 / 0.373 / 0.245, plain
  FedAvg's 0.013 / 0.002 / 0.092, trimmed-mean-only 0.205 / 0.000 / 0.025. Those ranges are wide; with three seeds no interval is claimed. Why survival rose
  is not established.
- The 30% ablation's full-pipeline row is the sweep's 30% point (same data, seed and attackers); it was not trained twice.

**Zero-day (leave one attack class out), full pool: mean over the held-out classes**

| Stage | Mean detection rate |
|---|---|
| Classifier alone | 0.735 / 0.757 / 0.723 (classes: 14, 14, 14) |
| Autoencoder alone | 0.681 / 0.728 / 0.590 (classes: 14, 14, 14) |
| Cascade | 0.910 / 0.944 / 0.895 (classes: 14, 14, 14) |

**Zero-day (leave one attack class out), full pool: mean over the held-out classes: per held-out class**

| Held-out class | Rows scored | Cascade detection | Classifier alone | Autoencoder alone |
|---|---|---|---|---|
| Backdoor | 24167 | 0.743 / 0.998 / 0.998 | 0.486 / 0.996 / 0.997 | 0.493 / 0.550 / 0.810 |
| DDoS_HTTP | 49768 | 0.879 / 0.932 / 0.885 | 0.695 / 0.764 / 0.719 | 0.572 / 0.698 / 0.560 |
| DDoS_ICMP | 68758 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 0.999 | 0.786 / 0.802 / 0.800 |
| DDoS_TCP | 50062 | 0.933 / 0.953 / 0.921 | 0.865 / 0.921 / 0.879 | 0.640 / 0.686 / 0.615 |
| DDoS_UDP | 121567 | 0.905 / 0.803 / 0.866 | 0.416 / 0.021 / 0.334 | 0.849 / 0.799 / 0.799 |
| Fingerprinting | 872 | 0.998 / 0.998 / 0.997 | 0.995 / 0.994 / 0.994 | 0.826 / 0.747 / 0.492 |
| MITM | 406 | 0.803 / 1.000 / 0.751 | 0.148 / 0.200 / 0.005 | 0.764 / 1.000 / 0.751 |
| Password | 50033 | 0.932 / 0.935 / 0.880 | 0.872 / 0.865 / 0.813 | 0.505 / 0.407 / 0.307 |
| Port_Scanning | 20213 | 0.999 / 0.993 / 0.992 | 0.998 / 0.988 / 0.989 | 0.570 / 0.745 / 0.409 |
| Ransomware | 9885 | 0.990 / 0.994 / 0.988 | 0.984 / 0.990 / 0.982 | 0.621 / 0.753 / 0.374 |
| SQL_injection | 50981 | 0.961 / 0.970 / 0.999 | 0.828 / 0.713 / 0.999 | 0.764 / 0.871 / 0.787 |
| Uploading | 37243 | 0.665 / 0.652 / 0.527 | 0.204 / 0.266 / 0.304 | 0.581 / 0.512 / 0.295 |
| Vulnerability_scanner | 50044 | 0.992 / 0.993 / 0.859 | 0.980 / 0.894 / 0.335 | 0.880 / 0.976 / 0.772 |
| XSS | 15172 | 0.943 / 0.991 / 0.867 | 0.823 / 0.986 / 0.767 | 0.680 / 0.650 / 0.483 |

**Reading zero-day (full pool).** Cascade detection of an unseen attack type averages 0.910 / 0.944 / 0.895 (earlier 0.943 / 0.952 / 0.952); classifier alone 0.735 /
0.757 / 0.723. Weakest: Uploading (0.527-0.665 for the cascade), then MITM (0.751-1.000; one connection) and, seed-dependent, Backdoor (0.743 in seed 42, 0.998 otherwise)
and Vulnerability_scanner (0.859 in seed 44). Every row of each held-out class is scored.

**Stealth attacker vs. sign-flip, full pool**

| Attackers | Sign-flip survival | Stealth survival | Sign-flip AE-alone recall | Stealth AE-alone recall | Stealth known-attack recall |
|---|---|---|---|---|---|
| 20% | 0.30 / 0.40 / 0.23 | 0.60 / n/a / n/a | 0.466 / 0.483 / 0.258 | 0.454 / n/a / n/a | 0.9956 / n/a / n/a |
| 30% | 0.50 / 0.55 / 0.62 | 0.73 / n/a / n/a | 0.490 / 0.373 / 0.245 | 0.427 / n/a / n/a | 0.9961 / n/a / n/a |
| 40% | 0.60 / 0.64 / 0.61 | 0.80 / n/a / n/a | 0.297 / 0.139 / 0.074 | 0.334 / n/a / n/a | 0.9949 / n/a / n/a |

**Pruning during federated training, full pool (no attackers)**

| Sparsity | Non-zero weights | Autoencoder-alone recall | Cascade macro-recall | Benign FPR |
|---|---|---|---|---|
| 0% | 9600 | 0.457 / 0.492 / 0.221 | 0.996 / 0.996 / 0.994 | 0.1182 / 0.0414 / 0.0352 |
| 50% | 4800 | 0.439 / n/a / n/a | 0.995 / n/a / n/a | 0.1400 / n/a / n/a |
| 70% | 2880 | 0.350 / n/a / n/a | 0.993 / n/a / n/a | 0.1201 / n/a / n/a |
| 80% | 1920 | 0.338 / n/a / n/a | 0.993 / n/a / n/a | 0.1451 / n/a / n/a |
| 90% | 960 | 0.198 / n/a / n/a | 0.993 / n/a / n/a | 0.1151 / n/a / n/a |

**Per-client z-score clip, final-round benign validation loss**

| Normalisation | seed 42 | seed 43 | seed 44 |
|---|---|---|---|
| clip 10 | 0.1292 | 0.05736 | 0.2644 |
| no clip | 0.242 | n/a | n/a |

**Reading stealth, pruning and clip (seed 42 only; the seed 43/44 jobs were not run).**
- *Stealth attacker.* Survival 0.60 / 0.73 / 0.80 against 0.30 / 0.50 / 0.60 for sign-flip; autoencoder-alone recall 0.454 / 0.427 / 0.334 against
  0.466 / 0.490 / 0.297 (no clear extra harm); known-attack recall >= 0.9949. Zero-day under this attacker was not measured.
- *Pruning during training.* Autoencoder-alone recall 0.457 -> 0.439 (50%) -> 0.350 (70%) -> 0.338 (80%) -> 0.198 (90%), cascade macro-recall 0.996 -> 0.993. At full
  scale pruning costs more than at 60k (70%: -0.107 against -0.056). *Pruning after training* (`results/full/pruning_post_c10_s42/`): autoencoder recall
  0.461 -> 0.375 (50%) -> 0.098 (70%), AUROC 0.892 -> 0.788 -> 0.495.
- *Clip.* Without the per-client z-score clip the final benign validation loss is 0.242 against 0.129 with it (1.9x); at 60k it was about 1,500x. The clip matters much
  less at full scale.

**Phase B on every attack capture (10 clients, seed 42, full-pool bundle): class chosen, confidence, deciding stage, packets flagged, action**

| Capture | Classified as | Confidence | Stage | Packets flagged | Action | Wall time |
|---|---|---|---|---|---|---|
| Backdoor attack | Backdoor | 0.997 | boosting | 24,543 / 24,914 | block | 12 s |
| DDoS HTTP Flood Attacks | DDoS_HTTP | 0.966 | boosting | 119,748 / 229,142 | block | 29 s |
| DDoS ICMP Flood Attacks | DDoS_ICMP | 1.000 | boosting | 2,914,156 / 2,914,356 | block | 232 s |
| DDoS TCP SYN Flood Attacks | DDoS_TCP | 0.999 | boosting | 2,020,023 / 2,020,152 | block | 211 s |
| DDoS UDP Flood Attacks | DDoS_UDP | 0.999 | boosting | 2,899,758 / 3,215,732 | block | 268 s |
| MITM ARP spoofing DNS Attack | Ransomware | 0.991 | boosting | 542 / 1,229 | block | 8 s |
| OS Fingerprinting attack | DDoS_ICMP | 0.980 | boosting | 1,134 / 1,176 | block | 9 s |
| Password attacks | Password | 0.957 | boosting | 919,469 / 1,053,893 | block | 130 s |
| Port Scanning attack | Port_Scanning | 0.999 | boosting | 22,495 / 23,329 | block | 12 s |
| Ransomware attack | Ransomware | 0.994 | boosting | 10,620 / 11,030 | block | 11 s |
| SQL injection attack | SQL_injection | 1.000 | boosting | 51,097 / 51,228 | block | 17 s |
| Uploading attack | Uploading | 0.999 | boosting | 37,592 / 37,644 | block | 15 s |
| XSS attacks | XSS | 0.999 | boosting | 15,677 / 16,215 | block | 12 s |
| Vulnerability scanner attack | Vulnerability_scanner | 0.996 | boosting | 262,922 / 265,827 | block | 60 s |

**Reading Phase B on all captures** (`scripts/reruns/run_phase_b_all.sh`; `logs/full/phase_b_all/`). All 14 captures end in a *block* decision with the
`priority=100,ip,nw_src=10.0.0.1 actions=drop` rule read back from the switch. **12 of 14 are classified as the right attack type**; the MITM capture is called
Ransomware (0.991; only 542 of its 1,229 packets flagged) and the OS-fingerprinting capture is called DDoS_ICMP (0.980). The replays are of the dataset's own
captures, so they demonstrate the pipeline; they are not a held-out test. The released Vulnerability-scanner capture is damaged (a record claims a 136 MB packet):
`extract_raw_fields` now uses the packets before the damage (265,827) and logs a warning; the other captures are intact. Largest replay: DDoS UDP, 3.2M packets, 268 s.

**Tests.** 244 passed, 1 skipped in 527 s (): the earlier 236 plus the grouped-split tests and the damaged-capture test; the second skip of earlier runs now executes because the real captures are present.

**New limitations from this run** (also in §10): packet-level false alarms are dominated by a few long connections; the trust filter excludes fewer attackers
at full scale; MITM cannot be split by connection and is scored only by zero-day and Phase B; the pipeline's classifier still starts from the 5% server set (the
full 1.43M-row classifier is a separate experiment, §8.10); stealth / pruning / clip are single-seed at full scale; the full-scale seeds are 42-44 only.

## 9. Do not cite (superseded numbers, with reason)

- Every real-data number from before `c1cc656` (label leak): Phase 5
  milestone numbers (90.5% accuracy, 0.907 weighted F1), leak-era
  boosting 0.983 accuracy, and the Phase 8 demo's reconstruction error
  0.71 → 0.47.
- Everything in `results/stale_pre_6bb8317/`: pre-clip, pre-MITM-repair,
  pre-attacker-count, MAD-only filter. Includes the ablation where plain
  FedAvg "survived" 30% attackers (val loss 0.36), and zero-day val
  losses of 6.6e13 / 3.6e5 (§4.3).
- The Phase 6 commit's (`854cd3b`) described results (e.g. FedAvg val
  loss ~1e16, recall 0.22): leak-era, accuracy-headline era.
- §8.4(a): only as the before/after comparison for the filter change,
  never as results.

---

## 10. Limitations (for the paper)

1. **Non-IID vs malicious data confound** (from CLAUDE.md, confirmed in
   practice). The filter targets corrupted *updates*. A client whose
   *data* is unusual but whose updates are honest can't be told apart
   from an honest heterogeneous client by cosine similarity. Under heavy
   skew, honest small-shard clients sit near 0 similarity and are
   sometimes excluded (~9% of honest client-rounds at 20% attackers,
   diagnostic §4.6).
2. **Late-round attackers look like noise.** After convergence, a
   small-shard attacker's sign-flipped delta is as near-orthogonal
   (+0.02…+0.11) as honest small-shard clients' (0.00…0.07). Direction
   tests can't separate them. Damage is bounded by the norm clip and
   trimmed mean, but the "excluded in most rounds" claim holds for one
   of the two attackers only (10/12 vs 5/12).
3. **Breakdown at 50% attackers** (§8.3): inherent to median-based references.
4. **Trimmed mean alone fails when attackers exceed the trim fraction**
   (15% per side over 10 clients trims one update per side, so 3
   colluding attackers get through).
5. **Two attack models tested** (sign-flip x5 with inflated count; and a white-box stealth attacker, §8.14d, which the
   filter mostly misses: survival 0.72-0.90). Other adaptive strategies (e.g. inner-product manipulation) and zero-day
   detection under the stealth attacker are untested.
6. **Backstop cost**: the 97th-percentile threshold gives ~3% benign FPR
   by construction. On known attacks the cascade gains ~0.012
   macro-recall over boosting alone at 30% attackers (§8.2).
7. **Privacy relaxation**: the incremental boosting update ships ≤50
   analyst-confirmed flagged rows per surviving client per update round
   (§4.4).
8. **Clients with no benign validation data** (Dirichlet skew) get an
   infinite threshold, so their AE never flags. Reported, not hidden.
9. **Tiny classes**: MITM (406 rows) and Fingerprinting (853) after
   dedup. Per-class numbers rest on few test rows.
10. **Mostly single seed.** Every Phase 6 number except the targeted
    multi-seed check (§8.3) is seed 42 only. That check found real
    seed-to-seed variance (AE-alone macro-recall ranged 0.19-0.42 across
    3 seeds at the same two fractions) and confirmed the 20%-vs-30%
    ordering doesn't hold consistently -- treat as noise, not a trend.
    `attack_macro_recall` was comparatively stable across seeds (0.83-0.88),
    so the headline cascade number is more trustworthy at a single seed
    than the AE-alone diagnostic column is. Seeds 43 and 44 now repeat
    the ablation, sweep and zero-day experiments (§8.14a), except the zero-day columns inside the ablation/sweep tables.
11. **Subsampled federated pool** (60k rows) in the runs of §8.1-8.14, for runtime. **Resolved in §8.15:** the main federated results now use the
    whole pool (1.89M rows) split by connection. The pipeline's bootstrap classifier still trains on the 5% server set (72-80k rows).
12. **Evaluation runs in-process**: same code, but no network effects;
    the real multi-process path is covered by tests and Phase A.
13. **Boosting broadcast size** (~11 MB/round) isn't in the
    communication-cost number (§8.6).
14. **Dataset corrections**: departing from the authors' preprocessing
    (§5.3) makes results not directly comparable to papers using the
    raw CSV. Argue that those papers are inflated, carefully.
15. **Novelty** rests on targeted searches only (CLAUDE.md caveat).
16. **Mitigation is not inline/streaming** (§8.7, found this session).
    Phase B classifies a capture only after tshark has extracted features
    from the whole thing -- for a replayed file, nearly the entire
    capture already matched the default NORMAL flow entry before the
    block rule appeared. Real-time, per-packet blocking is not what's
    currently measured or built; state this precisely rather than
    implying inline enforcement.
17. **DL-classifier comparison (§8.9) used a non-default sample.** The
    500k class-imbalance-capped sample changes the class distribution
    boosting itself normally sees (Normal ~10% instead of ~71%), so its
    benign FPR there (0.160) isn't comparable to §8.1/§8.2's numbers on
    the natural distribution. The comparison's *relative* result (boosting
    beats a comparable DL classifier) is sound; its *absolute* FPR
    numbers are sample-specific.
18. **Extended-feature trade-offs (§8.11).** Known-attack detection F1 is now
    higher for boosting alone (0.998) than for the cascade (0.961); MITM
    zero-day detection fell (0.894 -> 0.695); attacker survival at 40% rose
    (0.238 -> 0.362, single seed). svc_port is partly a testbed effect, and
    flow features summarise whole (<=120 s) records.

---

19. **Packet-level false alarms are dominated by a few long normal connections** (§8.15): 2.5%-16.3% of normal packets, but 0.34%-1.04% of normal connections and ~3% for the median client.
20. **The trust filter excludes fewer attackers at full scale** (survival 0.50-0.62 at 30%, earlier 0.12-0.27); cause not established.
21. **MITM cannot be split by connection** (one flow); it is scored only by zero-day and Phase B.
22. **Phase B captures are the dataset's own**, and the released Vulnerability-scanner capture is damaged (readable prefix used); two of 14 captures are classified as the wrong type (still blocked).
23. **Stealth, pruning and clip are single-seed at full scale**; the autoencoder backstop is weaker at full scale (recall alone 0.22-0.49).

---

## 11. Figures and tables to generate

- [x] (`deliverables/report/figures/poisoning_sweep.png`) Poisoning-resistance curve: x = malicious fraction; y = AE-alone
      macro-recall, zero-day macro-recall, attack macro-recall; second
      panel: malicious-client survival. (The harness writes
      `poisoning_resistance_sweep.png`; check its style.)
- [x] (`ablation.png`) Ablation table (§8.2 plus the CSV's zero-day, F1, convergence and
      bytes columns).
- [ ] Per-attack-type recall heatmap: variant × class (§8.2 table).
- [x] (`zero_day.png`, `zero_day_compare.png`) Zero-day per-class bar chart: boosting-only vs AE-alone vs
      cascade, 14 held-out classes (`zero_day_holdout.png` exists as a
      harness output; check it).
- [x] (`deliverables/report/figures/trust_mal02.png`, `trust_mal03.png`, real 10-client runs) Trust-score trajectories per client over rounds, honest vs
      attacker, 20% and 30% (from the strategy's round history /
      simulation records). Mark exclusion rounds by reason.
- [x] (right panel of `trust_mal0*.png`; shows the median-update similarity per round, honest vs attacker, not the MAD band itself) Similarity-distribution-per-round figure showing the MAD band
      widening past the attackers (§4.6). Strongest visual for the
      filter-change argument.
- [x] (`reconstruction_error.png`: normal vs known attacks with the threshold range; no zero-day class) Reconstruction-error distributions: benign vs known attacks vs
      zero-day class, per client, with the threshold line.
- [x] (`clip_val_loss.png`) Benign validation loss per round: clipped vs unclipped
      normalization (§4.3).
- [x] (`leak_auroc.png`) Data-quality figure: single-feature AUROC before/after the
      placeholder fix (§5.3.1).
- [x] (`partition_heatmap.png`) Per-client × per-class partition heatmap (seed 42, α = 0.3).
- [x] (`high_level_design.png`, `methodology_flowchart.png`) Architecture diagram: two phases, cascade, filter, SDN.
- [x] (`phase_b_timeline.png`) Phase B timeline: replay start → classification → flow rule
      (latency, once measured).

---

## 12. Pending (next phases will fill these)
- ~~Final CSVs of the Phase 6 regeneration~~ -- **done, §8.2/§8.3/§8.5**.
- ~~Real-data Phase A to completion -> bundle -> Phase B with a real
  pcap -> mitigation latency~~ -- **done, §8.1a/§8.7**.
- ~~Multi-seed repeats of the key points (at least 20% and 30%)~~ --
  **done for that specific point, §8.3**: the ordering doesn't hold,
  treat as noise. Full multi-seed repeats of every sweep/ablation point
  (not just this one flagged pair) are still not done.
- ~~Per-class precision/AUROC per stage~~ -- **done, §8.1**.
- ~~Phase 9's dashboard-live requirement~~ -- **done for the Training
  view, §8.8**, which also surfaced and fixed a real launch-command bug.
  The Live Simulation (Phase B) view specifically was not separately
  watched live this session -- worth doing once for completeness.
- ~~Commit this session's work to git~~ -- **done**; everything through
  2026-10-16 is committed and pushed (`4e19944`). Historical note: as of the 2026-09-27 update nothing from
  2026-09-25 through 2026-09-27 is committed yet.

### 12.2 Gap audit against CLAUDE.md and this file (2026-11-01)
Checked: CLAUDE.md "What done looks like", §0 status, §10 limitations, §11 figures, §12 pending.
- **Closed and evidenced.** (1) Phase 6 numbers exist (§8.2, §8.3, §8.5). (2) Phase 9 end-to-end run happened and is logged: `scripts/reruns/run_journey.sh` /
  `logs/journey/` (10 clients) and `scripts/reruns/run_clients20_real.sh` / `logs/clients20_real/` (20 clients); dashboard Training view watched live in a browser (§8.8).
  (3) Phase 10: `pytest` re-run after the 2026-11-01 changes, 233 passed, 2 skipped, 610.8 s (`logs/audit/pytest.log`). (4) Real 20-client run and repeat seeds (§8.13).
  (5) The cumulative results page (`docs/results.html`) now has the real runs (7, 7b) and the VMware host.
- **Live Simulation dashboard view.** Checked on 2026-11-01 with Phase B holding (`--hold-seconds 75`) and `tools/live_view_check.py` (Streamlit AppTest, auto-refresh off):
  bridge status ok, 1 switch, 1 classification, 1 device under mitigation, five tables populated, no errors (`logs/audit/live_view_check.log`).
  This is a headless render of the real bridge's responses, not a person watching it in a browser.
- **Closed on 2026-11-02, §8.15:** the whole federated system trains and is tested on all usable rows, split by connection; real Phase A at 10 and 20 clients, three seeds;
  sweep, ablation, zero-day, stealth, pruning, clip at full scale; Phase B on all 14 captures. Still open: the items below plus stealth/pruning/clip at seeds 43/44.
- **Closed on 2026-11-01 (later), §8.14:** (a) multi-seed repeats of the ablation, sweep and zero-day (zero-day columns inside the first two excepted);
  (b) the 20-client dip explained; (c) adaptive attacker tested; (g) weight pruning implemented and measured; (e) all §11 figures generated
  (zero-day class absent from the reconstruction-error figure); time-ordered split run; Phase B on the seed bundles; explainer PDFs regenerated.
- **Still open (honest list).** (d) no streaming/inline mitigation (§10.16); zero-day detection under the adaptive attacker and for pruned models;
  a second dataset; splits by *capture file* (the CSV does not record it; only a row-order time split was possible); the team's guide checklist
  was never received (handover note, open item 7).
- **Not part of CLAUDE.md but noted.** The multi-seed Phase A runs have no Phase B step; only the seed-42 20-client bundle was replayed.

### 12.1 [RESOLVED] Historical diagnosis: real multi-process Phase A OOM on the old VM (2026-09-25)
Kept in full below for the record -- this is real kernel-level diagnostic
work, not superseded by a simpler explanation, just resolved. **Resolution,
from the new machine (2026-09-27): setting `OMP_NUM_THREADS=1
MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
VECLIB_MAXIMUM_THREADS=1` before launching fixed it** -- the real Phase A
run then completed cleanly in ~5 minutes (§8.1a) on a VM with only
somewhat more RAM (12GB vs. this diagnosis's 7.2GB). This goes further
than this note's own `MALLOC_ARENA_MAX=2 OMP_NUM_THREADS=1` probe below
(logged as "not a fix") -- the missing piece was apparently the other
BLAS/OpenMP-family variables (MKL, OpenBLAS, NumExpr, vecLib), not
`OMP_NUM_THREADS` alone. The three numbered root-cause hypotheses below
were never individually verified or fixed (the broadcast-every-round
cost, LightGBM `Dataset` retention, orchestrator subprocess isolation) --
the thread-limit fix resolved the symptom without isolating which of
these, if any, was the actual mechanism. Worth revisiting if the same
class of problem recurs on tighter hardware.

Everything below this line is the original diagnosis, unedited.

Work moves to a new PC. Everything here is from the kernel log and
measurements on the old VM (7.2 GB RAM, 4 GB swap, 4 vCPUs), commit `41d958b`.

- **Every real Phase A attempt was killed by the kernel OOM killer**, not a
  Python error (logs just stop, no traceback): 2026-09-25 06:57, 07:18,
  07:22. The 07:22 victim was the **server** (anon RSS 1.50 GB); free swap
  was 120 kB. `41d958b`'s premise (the orchestrator was the problem) was
  only partly right.
- Per-process footprint at the 07:22 kill (RSS + swap, kernel dump):
  server ~1.54 GB; orchestrator ~0.94 GB (mostly swapped, idle during
  training, even after `41d958b`'s `del X, y`); each of the 10 clients
  ~0.56 GB, ~5.6 GB total. The clients are the bulk.
- A client's baseline before any work: ~430 MB (torch import ~210 MB,
  lightgbm import ~140 MB, parsed 300-tree boosting model ~35 MB).
- Probe: server + 2 real clients, 8 rounds, the saved `runs/phase_a` files:
  - Boosting update disabled: server flat at ~630 MB from round 2.
  - Update enabled (every 3 rounds): server 486 → 870 MB by round 8
    (+~150 MB at the round-3 update). Clients 700–810 MB each, also
    growing after update rounds.
  - `MALLOC_ARENA_MAX=2 OMP_NUM_THREADS=1`: server −~150 MB, clients
    −~50 MB. Not a fix.
- Likely causes, not yet fixed or verified:
  1. The ~11 MB boosting model goes into every client's fit config every
     round (`broadcast_every_n_rounds: 1`). Send it only when its version
     changes; clients keep the last copy. Also fixes §8.6 / limitation 13.
  2. `lgb.train` keeps its training `Dataset` (calibration + all alerts)
     referenced from each new booster on the server. Free it after training.
  3. The orchestrator keeps ~0.9 GB after data prep. Run prep in a
     short-lived subprocess.
- Shrinking the dataset doesn't help. The federated pool is already
  60k rows. A proportional 40k-row sample would leave ~18 Fingerprinting
  and ~22 MITM rows (counts from the raw CSV: 1,001 and 1,214), so ~1 of
  each in the 5% calibration set.
- Client count for a reduced demo run: trimmed mean trims
  `floor(0.15 × survivors)` per side (`fl_ids/robustness/aggregation.py`),
  i.e. nothing below 7 survivors. 5 clients (1 sign-flip attacker) shows
  all five pillars but leaves the trimmed mean inert. ~8 clients is the
  smallest count where it trims. Such a run is a demo, not citable.
- On the new PC: `git clone`; copy `archive.zip` (or re-download from
  Kaggle) into `data/raw/` with the same layout; copy
  `data/processed/MITM_reextracted.csv` or regenerate it (command in
  `configs/config.yaml`); recreate the venv from `requirements.txt`. The
  ablation CSVs and the ablation / poisoning-sweep logs are committed
  under `results/` (force-added past `.gitignore`), since they took
  ~8 hours to produce and §8.2–8.3 cite them.
- Order of remaining work: the fixes above → rerun the poisoning sweep
  and standalone zero-day **one at a time** (running both together caused
  the 04:48 kill) → multi-seed repeats → real 10-client Phase A → Phase B
  on its bundle (re-check the Backdoor→DDoS_HTTP misclassification, §8.7)
  → Phase 9 → Phase 10.
