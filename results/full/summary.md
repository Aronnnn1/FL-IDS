### Ablation at 30% sign-flip attackers, full pool, seeds 42 / 43 / 44

| Variant | Attack macro-recall | Autoencoder-alone recall | Benign FPR |
|---|---|---|---|
| full_pipeline | 0.995 / 0.997 / 0.995 | 0.490 / 0.373 / 0.245 | 0.1112 / 0.0653 / 0.0075 |
| autoencoder_only | 0.105 / 0.073 / 0.051 | 0.105 / 0.073 / 0.051 | 0.0473 / 0.0411 / 0.0445 |
| boosting_only | 0.990 / 0.989 / 0.982 | n/a / n/a / n/a | 0.0001 / 0.0001 / 0.0003 |
| plain_fedavg | 0.992 / 0.994 / 0.990 | 0.013 / 0.002 / 0.092 | 0.0947 / 0.0301 / 0.0301 |
| trimmed_mean_only | 0.995 / 0.995 / 0.993 | 0.205 / 0.000 / 0.025 | 0.1070 / 0.0261 / 0.0299 |

### Poisoning sweep, full pool

| Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival |
|---|---|---|---|
| 0% | 0.996 / 0.996 / 0.994 | 0.457 / 0.492 / 0.221 | n/a / n/a / n/a |
| 20% | 0.995 / 0.996 / 0.994 | 0.466 / 0.483 / 0.258 | 0.30 / 0.40 / 0.23 |
| 30% | 0.995 / 0.997 / 0.995 | 0.490 / 0.373 / 0.245 | 0.50 / 0.55 / 0.62 |
| 40% | 0.994 / 0.994 / 0.992 | 0.297 / 0.139 / 0.074 | 0.60 / 0.64 / 0.61 |
| 50% | 0.995 / 0.990 / 0.985 | 0.249 / 0.000 / 0.000 | 0.64 / 1.00 / 0.99 |

### Zero-day (leave one attack class out), full pool: mean over the held-out classes

| Stage | Mean detection rate |
|---|---|
| Classifier alone | 0.735 / 0.757 / 0.723 (classes: 14, 14, 14) |
| Autoencoder alone | 0.681 / 0.728 / 0.590 (classes: 14, 14, 14) |
| Cascade | 0.910 / 0.944 / 0.895 (classes: 14, 14, 14) |

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

### Stealth attacker vs. sign-flip, full pool

| Attackers | Sign-flip survival | Stealth survival | Sign-flip AE-alone recall | Stealth AE-alone recall | Stealth known-attack recall |
|---|---|---|---|---|---|
| 20% | 0.30 / 0.40 / 0.23 | 0.60 / n/a / n/a | 0.466 / 0.483 / 0.258 | 0.454 / n/a / n/a | 0.9956 / n/a / n/a |
| 30% | 0.50 / 0.55 / 0.62 | 0.73 / n/a / n/a | 0.490 / 0.373 / 0.245 | 0.427 / n/a / n/a | 0.9961 / n/a / n/a |
| 40% | 0.60 / 0.64 / 0.61 | 0.80 / n/a / n/a | 0.297 / 0.139 / 0.074 | 0.334 / n/a / n/a | 0.9949 / n/a / n/a |

### Pruning during federated training, full pool (no attackers)

| Sparsity | Non-zero weights | Autoencoder-alone recall | Cascade macro-recall | Benign FPR |
|---|---|---|---|---|
| 0% | 9600 | 0.457 / 0.492 / 0.221 | 0.996 / 0.996 / 0.994 | 0.1182 / 0.0414 / 0.0352 |
| 50% | 4800 | 0.439 / n/a / n/a | 0.995 / n/a / n/a | 0.1400 / n/a / n/a |
| 70% | 2880 | 0.350 / n/a / n/a | 0.993 / n/a / n/a | 0.1201 / n/a / n/a |
| 80% | 1920 | 0.338 / n/a / n/a | 0.993 / n/a / n/a | 0.1451 / n/a / n/a |
| 90% | 960 | 0.198 / n/a / n/a | 0.993 / n/a / n/a | 0.1151 / n/a / n/a |

### Per-client z-score clip, final-round benign validation loss

| Normalisation | seed 42 | seed 43 | seed 44 |
|---|---|---|---|
| clip 10 | 0.1292 | 0.05736 | 0.2644 |
| no clip | 0.242 | n/a | n/a |

### Real multi-process Phase A, full pool, split by connection

| Run | Phase A s | Attack macro-recall | Attack micro recall | Boosting-only micro recall | Benign FPR | Test rows | Clients with infinite threshold |
|---|---|---|---|---|---|---|---|
| 10 clients, seed 42 | 1844 | 0.9958 | 0.9974 | 0.9970 | 0.1275 | 288,416 | 1 |
| 10 clients, seed 43 | 1397 | 0.9947 | 0.9978 | 0.9971 | 0.0884 | 283,090 | 0 |
| 10 clients, seed 44 | 1754 | 0.9939 | 0.9956 | 0.9954 | 0.0248 | 288,366 | 2 |
| 20 clients, seed 42 | 1260 | 0.9981 | 0.9989 | 0.9981 | 0.0588 | 283,427 | 3 |
| 20 clients, seed 43 | 1063 | 0.9970 | 0.9980 | 0.9974 | 0.1628 | 292,222 | 2 |
| 20 clients, seed 44 | 1225 | 0.9972 | 0.9978 | 0.9972 | 0.1089 | 295,566 | 0 |
