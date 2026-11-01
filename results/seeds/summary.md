### Ablation (30% sign-flip attackers, 20 rounds): seeds 42 / 43 / 44

| Variant | Attack macro-recall | Autoencoder-alone recall | Benign FPR | Final validation loss |
|---|---|---|---|---|
| full_pipeline | 1.000 / 0.999 / 0.997 (mean 0.999) | 0.712 / 0.679 / 0.565 (mean 0.652) | 0.0309 / 0.0284 / 0.0320 (mean 0.0305) | 0.0282 / 0.0588 / 0.0204 |
| plain_fedavg | 0.998 / 0.997 / 0.994 (mean 0.996) | 0.002 / 0.000 / 0.000 (mean 0.001) | 0.0347 / 0.0317 / 0.0297 (mean 0.0321) | 4.99e+20 / 3.75e+23 / 1.97e+14 |
| trimmed_mean_only | 0.997 / 0.997 / 0.996 (mean 0.997) | 0.000 / 0.000 / 0.026 (mean 0.009) | 0.0334 / 0.0291 / 0.0337 (mean 0.0320) | 1.32e+04 / 9.78e+10 / 1.5 |
| autoencoder_only | 0.372 / 0.295 / 0.306 (mean 0.325) | 0.372 / 0.295 / 0.306 (mean 0.325) | 0.0301 / 0.0281 / 0.0325 (mean 0.0303) | 0.0498 / 0.072 / 0.0337 |
| boosting_only | 0.996 / 0.997 / 0.996 (mean 0.996) | n/a | 0.0002 / 0.0000 / 0.0005 (mean 0.0002) | n/a / n/a / n/a |

### Poisoning sweep (full pipeline): seeds 42 / 43 / 44

| Attackers | Attack macro-recall | Autoencoder-alone recall | Attacker survival |
|---|---|---|---|
| 0% | 1.000 / 0.999 / 0.997 (mean 0.999) | 0.737 / 0.765 / 0.612 (mean 0.705) | n/a |
| 20% | 0.999 / 0.999 / 0.996 (mean 0.998) | 0.736 / 0.739 / 0.618 (mean 0.698) | 0.10 / 0.03 / 0.23 (mean 0.12) |
| 30% | 1.000 / 0.999 / 0.997 (mean 0.999) | 0.712 / 0.679 / 0.565 (mean 0.652) | 0.12 / 0.12 / 0.27 (mean 0.17) |
| 40% | 1.000 / 0.998 / 0.997 (mean 0.998) | 0.691 / 0.620 / 0.537 (mean 0.616) | 0.36 / 0.31 / 0.44 (mean 0.37) |
| 50% | 0.997 / 0.997 / 0.995 (mean 0.996) | 0.000 / 0.000 / 0.000 (mean 0.000) | 1.00 / 0.99 / 0.97 (mean 0.99) |

### Zero-day (leave one attack class out): mean over the 14 classes, seeds 42 / 43 / 44

| Stage | Mean detection rate of the unseen class |
|---|---|
| Classifier alone | 0.801 / 0.748 / 0.791 (mean 0.780) |
| Autoencoder alone | 0.757 / 0.775 / 0.747 (mean 0.760) |
| Cascade | 0.943 / 0.952 / 0.952 (mean 0.949) |

| Held-out class | Cascade detection, seed 42 / 43 / 44 |
|---|---|
| Backdoor | 0.997 / 1.000 / 0.999 |
| DDoS_HTTP | 0.878 / 0.846 / 0.948 |
| DDoS_ICMP | 1.000 / 1.000 / 1.000 |
| DDoS_TCP | 0.989 / 0.997 / 0.997 |
| DDoS_UDP | 0.983 / 0.922 / 0.974 |
| Fingerprinting | 0.999 / 0.998 / 0.998 |
| MITM | 0.695 / 0.963 / 0.837 |
| Password | 0.967 / 0.972 / 0.950 |
| Port_Scanning | 0.999 / 0.999 / 0.999 |
| Ransomware | 0.999 / 0.999 / 0.999 |
| SQL_injection | 1.000 / 0.999 / 1.000 |
| Uploading | 0.716 / 0.677 / 0.665 |
| Vulnerability_scanner | 0.997 / 0.964 / 0.971 |
| XSS | 0.990 / 0.996 / 0.991 |
