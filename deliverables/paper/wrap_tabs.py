"""Post-process generated row files into complete tabular environments, and point sec6 at them."""
import re

specs = {
    "tab_prior.tex": ("lccc", "Model & Accuracy & Macro F1 & Train (s) \\\\"),
    "tab_zoo_top.tex": ("llccc", "Model & Family & F1 MQTTset & F1 DataSense & Composite \\\\"),
    "tab_zoo.tex": ("llccccrr", "Model & Family & Acc. & Macro F1 & Weighted F1 & Benign FPR & Train (s) & Predict ($\\mu$s/row) \\\\"),
    "tab_zoo_base.tex": ("lcccc", "Model & Acc.\\ (91) & Macro F1 (91) & Macro F1 (130) & Gain \\\\"),
}
for fn, (spec, head) in specs.items():
    body = open(fn, encoding="utf-8").read().strip()
    if body.startswith("\\begin{adjustbox}"):
        continue
    out = ("\\begin{adjustbox}{max width=\\linewidth}\n\\begin{tabular}{" + spec + "}\n\\toprule\n" + head + "\n\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n\\end{adjustbox}\n")
    open(fn, "w", encoding="utf-8").write(out)

s = open("sec6_models.tex", encoding="utf-8").read()
pat = re.compile(r"\\begin\{adjustbox\}\{max width=\\linewidth\}\s*\\begin\{tabular\}\{[^}]*\}.*?\\input\{(tab_[a-z_]+)\}.*?\\end\{adjustbox\}", re.S)
s = pat.sub(lambda m: "\\input{" + m.group(1) + "}", s)
open("sec6_models.tex", "w", encoding="utf-8").write(s)
print(s.count("\\input{tab_"))
