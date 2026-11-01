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

**Adaptive (stealth) attacker vs. sign-flip, seed 42, 20 rounds (source: results/adaptive/adaptive_attack.csv)**

| Attack | Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival | Final validation loss |
|---|---|---|---|---|---|
| sign_flip | 20% | 0.9993 | 0.730 | 0.10 | 0.026 |
| sign_flip | 30% | 1.0000 | 0.718 | 0.12 | 0.029 |
| sign_flip | 40% | 0.9997 | 0.663 | 0.36 | 0.021 |
| stealth | 20% | 0.9997 | 0.747 | 0.90 | 0.041 |
| stealth | 30% | 1.0000 | 0.741 | 0.72 | 0.040 |
| stealth | 40% | 0.9997 | 0.499 | 0.82 | 0.037 |

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

**Benign validation loss with and without the per-client z-score clip (source: results/clip/clip_comparison.csv)**

| Normalisation | Round 1 | Round 5 | Round 10 | Round 20 |
|---|---|---|---|---|
| clip 10 | 0.2047 | 0.04336 | 0.03999 | 0.03369 |
| no clip | 50.63 | 50.15 | 50 | 49.86 |

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

**Where the real-run macro-recall comes from (source: results/real_runs/<run>/, made by fl_ids.eval.bundle_report)**

| Run | Macro-recall | Micro recall | Fingerprinting test rows, recall | MITM test rows, recall | Clients with infinite threshold |
|---|---|---|---|---|---|
| 10 clients, seed 42 | 0.999 | 0.9992 | 3 rows, 1.00 | 3 rows, 1.00 | 0 |
| 10 clients, seed 43 | 0.999 | 0.9992 | 4 rows, 1.00 | 4 rows, 1.00 | 1 |
| 10 clients, seed 44 | 0.996 | 0.9960 | 4 rows, 1.00 | 5 rows, 1.00 | 1 |
| 20 clients, seed 42 | 0.978 | 0.9964 | 4 rows, 0.75 | 1 rows, 1.00 | 3 |
| 20 clients, seed 43 | 0.999 | 0.9992 | 2 rows, 1.00 | 3 rows, 1.00 | 2 |
| 20 clients, seed 44 | 0.999 | 0.9988 | 2 rows, 1.00 | 3 rows, 1.00 | 2 |

**Real multi-process Phase A with sign-flip attackers (10 clients, 20 rounds, seed 42; source: runs/attack_runs/)**

| Attackers | Attacker clients | Attacker client-rounds excluded | Honest client-rounds excluded | Attack macro-recall | Benign FPR |
|---|---|---|---|---|---|
| 20% | 0,7 | 36 of 40 | 0 of 160 | 0.998 | 0.0335 |
| 30% | 0,6,9 | 52 of 60 | 0 of 140 | 0.999 | 0.0317 |

**Phase B on the multi-seed bundles, Backdoor_attack.pcap, every run ends with a drop rule read back from the switch (source: logs/multiseed/status_phase_b.log)**

| Bundle | Class | Confidence | Packets flagged | Phase B time |
|---|---|---|---|---|
| 10 clients, seed 43 | Backdoor | 0.997 | 24244 / 24914 | 10.8 s |
| 10 clients, seed 44 | Backdoor | 0.998 | 24914 / 24914 | 8.3 s |
| 20 clients, seed 43 | Backdoor | 0.997 | 24848 / 24914 | 11.1 s |
| 20 clients, seed 44 | Backdoor | 0.997 | 24914 / 24914 | 9.1 s |
