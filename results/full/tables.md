**Ablation at 30% sign-flip attackers, full pool, seeds 42 / 43 / 44**

| Variant | Attack macro-recall | Autoencoder-alone recall | Benign FPR |
|---|---|---|---|
| full_pipeline | 0.995 / 0.997 / 0.995 | 0.490 / 0.373 / 0.245 | 0.1112 / 0.0653 / 0.0075 |
| autoencoder_only | 0.105 / 0.073 / 0.051 | 0.105 / 0.073 / 0.051 | 0.0473 / 0.0411 / 0.0445 |
| boosting_only | 0.990 / 0.989 / 0.982 | n/a / n/a / n/a | 0.0001 / 0.0001 / 0.0003 |
| plain_fedavg | 0.992 / 0.994 / 0.990 | 0.013 / 0.002 / 0.092 | 0.0947 / 0.0301 / 0.0301 |
| trimmed_mean_only | 0.995 / 0.995 / 0.993 | 0.205 / 0.000 / 0.025 | 0.1070 / 0.0261 / 0.0299 |

**Poisoning sweep, full pool**

| Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival |
|---|---|---|---|
| 0% | 0.996 / 0.996 / 0.994 | 0.457 / 0.492 / 0.221 | n/a / n/a / n/a |
| 20% | 0.995 / 0.996 / 0.994 | 0.466 / 0.483 / 0.258 | 0.30 / 0.40 / 0.23 |
| 30% | 0.995 / 0.997 / 0.995 | 0.490 / 0.373 / 0.245 | 0.50 / 0.55 / 0.62 |
| 40% | 0.994 / 0.994 / 0.992 | 0.297 / 0.139 / 0.074 | 0.60 / 0.64 / 0.61 |
| 50% | 0.995 / 0.990 / 0.985 | 0.249 / 0.000 / 0.000 | 0.64 / 1.00 / 0.99 |

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
