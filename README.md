# FL-IDS: Federated Learning-Based Intrusion Detection System

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
tables, per-class breakdowns and caveats are in `PAPER_NOTES.md`; headline
numbers only here.

- **Ablation** (30% sign-flip attackers, 20 rounds, seed 42): full cascade
  gets 0.887 attack macro-recall and 0.731 zero-day macro-recall, vs.
  boosting-only's 0.875 / 0.518 and autoencoder-only's 0.191 / 0.325. The
  cascade barely beats boosting alone on *known* attacks, but the
  autoencoder backstop nearly doubles zero-day detection — that's where
  its value shows up, not in the headline cascade number.
- **Poisoning sweep** (0/20/30/40/50% sign-flip attackers): attack
  macro-recall stays in a tight 0.878–0.887 band through 40% attackers.
  The trust filter is what keeps the federated autoencoder usable —
  without it (plain FedAvg), autoencoder-alone recall collapses to 0
  even at 30%. At 50% the coordinate-median-based filter itself breaks
  down (malicious-client survival jumps to 96%) — an expected limit of
  median-based defenses, not a bug.
- **Zero-day (leave-one-attack-class-out)**, all 14 classes, 0%
  attackers: the cascade is at least as good as `max(boosting-only,
  autoencoder-alone)` for every single held-out class. The backstop's
  value is starkest on classes boosting has zero training signal for —
  MITM (0% boosting-only → 89% cascade), DDoS_UDP (9% → 90%),
  Vulnerability_scanner (10% → 84%).
- **Real Phase A run** (real Flower server + 10 real client processes,
  not the in-process simulation used for the sweeps above): 0.889 attack
  macro-recall, 0.0346 benign FPR — closely matches the in-process
  simulation's numbers, a useful cross-check that the faster simulation
  is representative.
- **Phase B**, real Phase A bundle, `Backdoor_attack.pcap` replayed:
  correctly classified as Backdoor (0.997 confidence, boosting stage
  alone), installed a real `drop` flow rule, verified via the switch's
  own flow table. Mitigation is capture-level, not per-packet/streaming
  — see Known limitations.
- **Boosting vs. a supervised DL classifier** (separate from the ablation
  above; see "Running" section): boosting wins decisively as a
  classifier too, not just as a detector — 0.887 vs. 0.621 macro F1 on
  the same 500k-row sample. Full breakdown in `PAPER_NOTES.md` §8.9.
