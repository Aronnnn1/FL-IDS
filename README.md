# FL-IDS: Federated Learning-Based Intrusion Detection System

**Status: complete (2026-10-16).** Every phase is implemented, run on the
real data and verified end to end; the paper is being written.

A federated intrusion detection system for IoT/IIoT traffic (Edge-IIoTset).
Five parts, each doing real work:

1. **IDS cascade**: a LightGBM classifier labels known attack types. Traffic
   it calls normal (or isn't confident about) goes to a client-side
   autoencoder, whose reconstruction error flags anything unlike benign
   traffic as `anomalous`. That second stage is the zero-day backstop.
2. **Federated learning** (Flower): the autoencoder is trained across
   non-IID clients in real separate processes. Raw traffic stays on clients.
3. **Autoencoder**: trained only on the traffic boosting passes as normal,
   with a per-client anomaly threshold (97th percentile of benign
   validation error) recalibrated every round.
4. **Cosine-similarity trust filter**: the server scores each client's
   weight *delta* against the round's median delta. It excludes per-round
   MAD outliers, updates pointing away from the consensus (cosine < 0),
   and clients whose EMA trust has fallen below 0.5. It clips the
   survivors' norms to 2x the round median and aggregates them with a
   trimmed mean.
5. **SDN mitigation** (Mininet + Open vSwitch, OpenFlow 1.3): live
   classifications of replayed `.pcap` captures become real flow rules
   (drop, or an OpenFlow meter for rate limiting).

`CLAUDE.md` holds the full specification, literature grounding and phased
build plan. Git history records which commit met which milestone.

## Repository layout

```
fl_ids/
  data/           Component 1: load, clean, encode, Dirichlet partition, per-client normalization;
                  repair.py re-extracts the column-shifted MITM capture
  models/         Components 2, 3: boosting classifier (+ incremental update), autoencoder,
                  cascade decision rule (the one implementation every stage uses)
  fl/             Components 4, 7, 8: Flower client, trust-filtered Strategy, server, process launch
  robustness/     Components 5, 6: cosine/MAD/norm trust filter, trimmed mean, sign-flip test attacker
  sdn/            Components 9, 10: mitigation REST bridge, OpenFlow 1.3 controller (os-ken),
                  Mininet topology, live tshark feature extraction, live inference
  orchestration/  Component 11: Phase A / Phase B entrypoints, model bundle
  eval/           Component 12: per-stage metrics, ablation, poisoning sweep, zero-day experiment
  dashboard/      Component 13: Streamlit dashboard (training and live-simulation views)
  utils/          Config loading, logging setup
configs/config.yaml   Every tunable parameter
tests/                pytest unit and integration tests
```

Results and artefacts (committed, although `.gitignore` excludes these
folders by default):

```
results/                  Federated results with the original 91 features (CSV, PNG, logs)
results/extended/         The same experiments with the current 130 features
experiments/accuracy/     Classifier-accuracy experiment: train_eval.py, build_features.py,
                          results/ (metrics JSON, LightGBM models, test-set predictions),
                          results_v1/ (first, superseded round), run logs
logs/                     Logs of the experiment runs (logs/extended/ = 130 features)
saved_models/phase_a/     Phase A model bundle (130 features); phase_a_base91/ = 91 features
runs/, runs_base91/       Real Phase A / Phase B run records: server and client logs, history,
                          config, Phase B result (client data slices not included)
scripts/reruns/           Queue scripts used to re-run every experiment (run from the repo root)
deliverables/             Presentation, project report (LaTeX + PDF), plain-language explainers
docs/                     The results website (GitHub Pages)
```

Not committed: the Edge-IIoTset dataset (`data/raw/`, see Setup), anything
derived from it (`data/processed/`, `experiments/accuracy/features.parquet`,
the per-client `.npz` slices in `runs*/`), and the virtual environment.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

System packages for Phase B: Mininet, Open vSwitch, `tshark`, `tcpreplay`.

**Dataset** (not committed): download Edge-IIoTset from Kaggle
(`mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot`). Put
`DNN-EdgeIIoT-dataset.csv` in `data/raw/` and the per-device `.pcap`
captures in `data/raw/pcaps/`. Then regenerate the repaired MITM rows (see
"Data corrections" below):

```bash
python -m fl_ids.data.repair --pcap "data/raw/pcaps/MITM (ARP spoofing + DNS) Attack.pcap" \
  --attack-type MITM --output data/processed/MITM_reextracted.csv
```

**Root access for Phase B.** Mininet needs root. The topology script
takes no arguments (it reads its parameters from a fixed file in `/tmp`),
so one narrow sudoers rule covers it:

```
<user> ALL=(root) NOPASSWD: /usr/bin/python3 /path/to/FL-IDS/fl_ids/sdn/topology.py
```

**Where the work runs.** All FL-IDS work (data, training, results) runs inside an
isolated Ubuntu 26.04 VM so that attack captures stay off the host. A VMware
Workstation build (24 GB RAM, which holds a real 20-client run) is scripted in
`D:\FL-IDS-VM\setup\` on the Windows host: `setup_vm.py` creates and provisions
it, `verify_vm.sh` checks Phase A and Phase B. Real multi-process runs beyond
the default 10 clients:

```bash
bash scripts/reruns/run_clients20_real.sh   # 1 server + 20 client processes, then Phase B (about 4.5 min)
bash scripts/reruns/run_multiseed.sh        # seeds 43, 44 at 10 and 20 clients (about 20 min)
python3 tools/summarize_real_runs.py        # -> results/real_runs/summary.{json,md}
```

Follow-up experiments (2026-11-01; results in `PAPER_NOTES.md` section 8.14 and `results/followups/`):

```bash
python3 tools/run_sharded_seeds.py --workers 14       # ablation, sweep, zero-day at seeds 43/44, one process per job (about 30 min on 20 vCPUs)
python3 tools/summarize_seeds.py                     # -> results/seeds/summary.{md,json}
python -m fl_ids.eval.adaptive_attack --num-rounds 20   # stealth vs sign-flip attackers
python -m fl_ids.eval.pruning_fl --num-rounds 20        # weight pruning during federated training
python -m fl_ids.eval.pruning --config-path configs/config_vmware_check.yaml \
  --artifact-dir saved_models/vmware_check_phase_a --run-dir runs/vmware_check/phase_a   # post-training pruning
python -m fl_ids.eval.clip_comparison --num-rounds 20   # with / without the per-client z-score clip
python -m fl_ids.eval.bundle_report --config-path <cfg> --artifact-dir <bundle> --run-dir <run>  # per-class / per-client breakdown
python experiments/accuracy/train_eval.py full --temporal --balance --seed 42   # time-ordered split
python3 tools/build_followups.py                     # tables for the notes, report and results page
```

## Running

```bash
pytest                                        # full suite (~7 min; real-data tests skip without the dataset)

python -m fl_ids.orchestration.phase_a        # Phase A: FL training -> saved_models/phase_a
python -m fl_ids.orchestration.phase_a --malicious-fraction 0.3   # with sign-flip attackers

python -m fl_ids.orchestration.phase_b --pcap "data/raw/pcaps/Backdoor_attack.pcap" --hold-seconds 60

streamlit run fl_ids/dashboard/app.py         # live dashboard for either phase

python -m fl_ids.eval.ablation --num-rounds 20         # results/ablation_*.csv
python -m fl_ids.eval.poisoning_sweep --num-rounds 20  # results/poisoning_resistance_sweep.{csv,png}
python -m fl_ids.eval.zero_day --num-rounds 20         # results/zero_day_holdout.{csv,png}

python -m fl_ids.eval.classifier_comparison            # boosting vs. a supervised DL classifier, see below
```

Run the poisoning sweep and zero-day scripts one at a time, not concurrently
— both hold the full dataset in memory independently, and running them
together on a memory-constrained machine can OOM a long run mid-way.

### Boosting vs. a supervised DL classifier

`fl_ids.eval.classifier_comparison` answers a different question from the
`autoencoder_only` ablation variant above: not "is the *unsupervised*
autoencoder a viable standalone detector" (already covered), but "of two
*supervised* classifiers trained on the same attack-type labels, which is
more accurate" — LightGBM against a small dense MLP
(`fl_ids.models.dl_classifier`), both scored the same way. It runs on a
class-imbalance-capped sample (`fl_ids.data.sampling`, default 500,000
rows — every row of scarce classes kept, common classes capped toward an
even per-class share, no synthetic oversampling) rather than the full
dataset, so it's quick to iterate on. See `PAPER_NOTES.md` §8.9 for the
full results and caveats.

Phase A runs a real Flower server and one OS process per client, then
saves a self-describing bundle: boosting model, global autoencoder
weights, each client's scaler and anomaly threshold, cascade settings,
held-out metrics and provenance. Phase B rebuilds the models from that
bundle, not from the current config. It brings up Mininet with one host
per FL client (`h<i+1>` is client `i`, scored with that client's scaler
and threshold), replays the capture with `tcpreplay`, classifies the
traffic, posts the verdict to the mitigation bridge, and checks the
switch's flow table for the resulting rule.

The evaluation scripts drive the same client, attacker and aggregation
code in-process instead of over gRPC, so dozens of training runs stay
practical. The multi-process path is covered by the integration tests
and by Phase A itself.

## Design decisions and departures from the dataset authors' recipe

- **Boosting labels come from a server-held calibration set** (5% of the
  data). Boosting is trained on it before round 1, so clients never
  filter with an untrained model, and it's broadcast to clients in each
  round's `configure_fit` payload.
- **Incremental boosting update, with a privacy trade-off.** Every 3
  rounds, clients that survived the trust filter surface up to 50 rows
  their autoencoder flagged, with analyst-confirmed labels. Boosting
  continues training on them (`init_model`), or retrains when they
  introduce a class it has never seen (continued training can't learn a
  new class). This relaxes "raw traffic never leaves a client" for
  capped, confirmed alerts only.
- **Boosting sees raw features; the autoencoder sees per-client
  normalized features.** Under non-IID skew, a client's own scaler can
  move a feature by orders of magnitude, which breaks a shared tree
  model's split thresholds.
- **Per-client z-scores are clipped at ±10** (`data.normalized_clip`).
  Counter-like features (`udp.stream`, `tcp.seq`) can barely vary within
  one client's shard. Ordinary rows then land 10^3–10^4 std out and swamp
  that client's reconstruction error.
- **The SDN controller is built on os-ken**, the maintained OpenStack
  fork of Ryu. The spec expected an existing custom controller; none was
  available, so one was built on os-ken rather than on abandoned Ryu.

- **Service-port, content and flow features** (`fl_ids/data/features.py`,
  `data.extended_features`). In the HTTP-family attacks most packets are
  content-free ACKs, identical across attacks. The server-side port,
  numeric payload/URI features and per-connection aggregates (60 s idle /
  120 s active timeout) separate them. IP addresses, timestamps and
  ephemeral ports only group packets into flows and are never features.
  Phase B derives the same features live. `extended_features: false`
  reproduces the original 91-feature pipeline.

### Data corrections

- **Placeholder label leak.** The "field doesn't apply" placeholder in the
  categorical columns is spelled `0` in some source captures and `0.0` in
  others, and the spelling follows the label: after one-hot encoding,
  `mqtt.topic_0.0` alone separates benign from attack with AUROC 1.0.
  Both spellings are canonicalized to `0` before encoding. A test guards
  that no single feature exceeds AUROC 0.9 (the maximum is now ~0.71).
- **Column-shifted MITM rows.** The authors' MITM CSV has values under
  the wrong column names (its `tcp.seq` is really `udp.time_delta`).
  Those rows are replaced by a re-extraction of the authors' own pcap,
  with the same field list and encoding. Modbus has the same fault, but
  none of its rows are in the training CSV. Its live traffic is therefore
  out of distribution, so don't use it as the benign Phase B device.
- **tshark 4.x output differences.** Newer tshark prints booleans as
  `True`/`False` and shortens hex values. Live extraction maps both back
  to the authors' spelling, so live rows encode the same way as training
  rows.

## Known limitations

- **Non-IID vs. malicious data.** The trust filter targets corrupted
  *updates* (sign-flip / scaling). A client whose local *data* is
  unusual but whose updates are honest looks like any other heterogeneous
  client. Cosine similarity can't separate the two, and under heavy skew
  the MAD filter sometimes excludes honest small-shard clients for a
  round.
- **Late-round attackers can look like honest noise.** The filter
  excludes a client if its similarity is a per-round MAD outlier, if its
  update points away from the consensus (cosine < 0, the FLTrust
  precedent), or if its EMA trust falls below 0.5. MAD alone let 20%
  sign-flip attackers through about 78% of rounds, because honest non-IID
  spread widened its band past them. With all three checks, attacker
  exclusion rises to about 62% of attacker-rounds. The misses come once
  the model has converged: a small-shard attacker's flipped delta is as
  near-orthogonal as an honest small-shard client's, so it slips through
  but barely moves the model, and the norm clip plus trimmed mean bound
  it. The cost is honest near-zero clients excluded in about 9% of
  client-rounds.
- **Trimmed mean alone doesn't survive attackers above its trim
  fraction.** With a 15% trim over 10 clients, one update is trimmed from
  each side, so 3 colluding sign-flip attackers get through. The ablation
  shows this on purpose.
- **Cost of the backstop.** The 97th-percentile threshold puts roughly 3%
  of benign traffic above threshold by construction. The cascade trades
  that false-positive rate for detection of attacks boosting has never
  seen.
- **Novelty claim.** No single published system combining all five parts
  turned up in targeted searches. That isn't a systematic review, so
  don't state novelty as settled without one.
- **Mitigation is capture-level, not streaming.** Phase B classifies a
  capture only after tshark has extracted features from all of it — for
  a replayed pcap, most of the capture matches the default allow rule
  before the block rule appears. This isn't inline, per-packet blocking
  of a live stream; state that precisely rather than implying real-time
  enforcement.

## Results

Regenerated after the data corrections above. All real-data numbers from
before commit `c1cc656` are leak-inflated and must not be cited. Full
tables, per-class breakdowns and caveats are in `PAPER_NOTES.md` (§8.10
classifier, §8.11 federated pipeline); headline numbers only here. The
current pipeline uses 130 features (the 91 base features plus the
service-port, content and flow features of `fl_ids/data/features.py`);
numbers in brackets are the original 91-feature results (`results/`), kept
for comparison. New results are in `results/extended/`.

- **Classifier** (LightGBM on all 1.99M rows: 1.43M train, 397k test,
  connections held out of training, 3 seeds): 99.7% accuracy, 0.983–0.985
  macro F1 [96.4%, 0.889].
- **Data scale:** the federated system trains on ~125k rows (79,430-row
  server calibration set + 45,474 client training rows from the 60k pool),
  not the full dataset; see PAPER_NOTES §5.5.
- **Real Phase A run** (real Flower server + 10 client processes):
  0.999 attack macro-recall [0.889], 0.035 benign FPR [0.035];
  bootstrap boosting accuracy 0.997 [0.963].
- **Zero-day (leave-one-attack-class-out)**, all 14 classes, 0% attackers:
  cascade 0.943 macro-recall [0.736], boosting-only 0.801 [0.533],
  autoencoder-alone 0.757 [0.493]. Two classes got worse: MITM
  0.894 → 0.695, and Uploading for boosting alone (0.487 → 0.080; cascade
  still 0.517 → 0.716).
- **Ablation** (30% sign-flip attackers, 20 rounds, seed 42): full cascade
  1.000 attack / 0.930 zero-day macro-recall [0.887 / 0.731], vs.
  boosting-only's 0.996 / 0.795 and autoencoder-only's 0.372 / 0.577.
  Without the trust filter (plain FedAvg, trimmed mean only) the
  autoencoder is poisoned (recall ~0, loss diverges) and zero-day falls
  back to boosting's ~0.80. On *known* attacks boosting alone now has the
  better detection F1 (0.998 vs 0.961): the backstop's ~3% false alarms
  cost more than it adds there; its value is on unseen attacks.
- **Poisoning sweep** (0/20/30/40/50% sign-flip attackers): attack
  macro-recall 0.997–1.000 at every fraction, zero-day 0.90–0.94 up to
  40%. Attacker survival 0.10 / 0.12 / 0.36 at 20 / 30 / 40% [0.28 / 0.32 /
  0.24]. At 50% the coordinate-median-based filter breaks down as before
  (survival 100%), an expected limit of median-based defences.
- **Phase B**, new bundle, `Backdoor_attack.pcap` replayed: Backdoor
  (0.997 confidence, boosting stage), 24,669 of 24,914 packets flagged,
  real `drop` flow rule verified in the switch's own flow table. Live
  extraction derives the same features as training: 99.8% of live rows
  match the capture's training rows exactly. Mitigation is still
  capture-level, not per-packet/streaming (see Known limitations).
- **Boosting vs. a supervised DL classifier** (91 features, 500k-row
  sample): 0.887 vs. 0.622 macro F1. Full breakdown in `PAPER_NOTES.md` §8.9.
