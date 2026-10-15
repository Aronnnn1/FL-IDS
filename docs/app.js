(function () {
  "use strict";
  var D = window.FLIDS, FL = window.FLCommon;
  function $(id) { return document.getElementById(id); }
  function get(obj, path) { return path.split(".").reduce(function (o, k) { return o == null ? o : o[k]; }, obj); }

  document.addEventListener("DOMContentLoaded", function () {

    // ---- data-bound numbers (summary.json) ----
    Array.prototype.forEach.call(document.querySelectorAll("[data-bind]"), function (el) {
      var v = get(D.summary, el.getAttribute("data-bind"));
      if (typeof v === "number") el.textContent = v.toFixed(parseInt(el.getAttribute("data-d") || "3", 10));
    });

    // ---- data-bound numbers (classifier-accuracy runs) ----
    var ACC = D.accuracy;
    Array.prototype.forEach.call(document.querySelectorAll("[data-acc]"), function (el) {
      var v = get(ACC.runs, el.getAttribute("data-acc"));
      if (typeof v !== "number") return;
      if (el.hasAttribute("data-pct")) el.textContent = (v * 100).toFixed(parseInt(el.getAttribute("data-pct"), 10)) + "%";
      else if (el.hasAttribute("data-int")) el.textContent = FL.int(Math.round(v));
      else el.textContent = v.toFixed(parseInt(el.getAttribute("data-d") || "3", 10));
    });
    var mitmF1 = ACC.finalRandom.perClass.MITM["f1-score"].toFixed(3);
    Array.prototype.forEach.call(document.querySelectorAll("#mitm-random, .mitm-random-2"), function (el) { el.textContent = mitmF1; });

    // final confusion matrix without classes that have no test rows (MITM is one connection)
    var fin = ACC.final, keep = [];
    fin.cm.forEach(function (row, i) { if (row.reduce(function (a, b) { return a + b; }, 0) > 0) keep.push(i); });
    var cmFinal = keep.map(function (i) { return keep.map(function (j) { return fin.cm[i][j]; }); });
    var finalNames = keep.map(function (i) { return fin.classes[i]; });

    // ---- comparison table ----
    (function () {
      var b = D.summary.boosting, d = D.summary.dl_classifier;
      function row(name, bv, dv, gap, gapCls) {
        return "<tr><td>" + name + "</td><td>" + bv + "</td><td>" + dv + "</td><td class='" + (gapCls || "") + "'>" + gap + "</td></tr>";
      }
      var sg = function (x) { return (x >= 0 ? "+" : "&minus;") + Math.abs(x).toFixed(3); };
      var h = '<div class="table-wrap"><table><thead><tr><th>Metric</th><th>Boosting</th><th>DL classifier</th><th>Gap</th></tr></thead><tbody>';
      h += row("Accuracy", b.accuracy.toFixed(4), d.accuracy.toFixed(4), sg(b.accuracy - d.accuracy), "num-pos");
      h += row("Macro F1", b.macro_f1.toFixed(4), d.macro_f1.toFixed(4), sg(b.macro_f1 - d.macro_f1), "num-pos");
      h += row("Weighted F1", b.weighted_f1.toFixed(4), d.weighted_f1.toFixed(4), sg(b.weighted_f1 - d.weighted_f1), "num-pos");
      h += row("Benign false-positive rate", b.benign_fpr.toFixed(4), d.benign_fpr.toFixed(4), sg(b.benign_fpr - d.benign_fpr) + " (lower is better)", "num-pos");
      h += row("Train time", b.train_seconds.toFixed(1) + " s", d.train_seconds.toFixed(1) + " s", "&mdash;");
      h += row("Model size", (b.model_size_bytes / 1e6).toFixed(1) + " MB (300 trees &times; 15 classes)", FL.int(d.num_parameters) + " parameters", "&mdash;");
      h += "</tbody></table></div>";
      $("compare-table").innerHTML = h;
    })();

    // ---- per-class recall bars ----
    var byStage = { boost: {}, dl: {} };
    D.perClassCompare.forEach(function (r) {
      (r.stage === "boosting_alone" ? byStage.boost : byStage.dl)[r["class"]] = r;
    });
    (function () {
      var classes = D.classNames.slice().sort(function (a, b) {
        return (byStage.boost[b].recall - byStage.dl[b].recall) - (byStage.boost[a].recall - byStage.dl[a].recall);
      });
      var el = $("recall-chart");
      classes.forEach(function (c) {
        var bo = byStage.boost[c].recall, dl = byStage.dl[c].recall;
        var w = document.createElement("div"); w.className = "bar-metric";
        w.innerHTML = '<div class="metric-name">' + c + '</div>' +
          '<div class="bar-row"><span class="bar-label">Boost</span><div class="bar-track"><div class="bar-fill boost" style="width:' + (bo * 100).toFixed(1) + '%"></div></div><span class="bar-val">' + bo.toFixed(3) + '</span></div>' +
          '<div class="bar-row"><span class="bar-label">DL</span><div class="bar-track"><div class="bar-fill dl" style="width:' + (dl * 100).toFixed(1) + '%"></div></div><span class="bar-val">' + dl.toFixed(3) + '</span></div>';
        el.appendChild(w);
      });
    })();

    // ---- confusion matrices ----
    var mode = "count";
    function drawCm() {
      FL.heatmap($("cm-boost"), D.cmBoost, D.classNames, mode);
      FL.heatmap($("cm-dl"), D.cmDl, D.classNames, mode);
      FL.heatmap($("cm-final"), cmFinal, finalNames, mode);
      $("cm-bar").style.background = FL.heatScaleCss();
    }
    drawCm();
    FL.onTheme(drawCm);
    Array.prototype.forEach.call(document.querySelectorAll("#cm-mode button"), function (b) {
      b.addEventListener("click", function () {
        mode = b.getAttribute("data-mode");
        Array.prototype.forEach.call(document.querySelectorAll("#cm-mode button"), function (x) { x.classList.toggle("on", x === b); });
        drawCm();
      });
    });

    // share of all errors that lie inside the HTTP-family cluster
    var cluster = ["DDoS_HTTP", "Normal", "Password", "SQL_injection", "Uploading", "XSS"].map(function (n) { return D.classNames.indexOf(n); });
    function errShare(m) {
      var tot = 0, inC = 0;
      m.forEach(function (row, i) { row.forEach(function (v, j) {
        if (i === j) return; tot += v;
        if (cluster.indexOf(i) >= 0 && cluster.indexOf(j) >= 0) inC += v;
      }); });
      return { tot: tot, inC: inC, pct: (100 * inC / tot) };
    }
    var sb = errShare(D.cmBoost), sd = errShare(D.cmDl);
    $("err-share-boost").textContent = sb.pct.toFixed(0) + "% (" + FL.int(sb.inC) + " of " + FL.int(sb.tot) + ")";
    $("err-share-boost-2").textContent = sb.pct.toFixed(0) + "%";
    $("err-share-dl").textContent = sd.pct.toFixed(0) + "% (" + FL.int(sd.inC) + " of " + FL.int(sd.tot) + ")";
    (function () {
      var cl = ["DDoS_HTTP", "Normal", "Password", "SQL_injection", "Uploading", "XSS"].map(function (n) { return finalNames.indexOf(n); });
      var tot = 0, inC = 0;
      cmFinal.forEach(function (row, i) { row.forEach(function (v, j) {
        if (i === j) return; tot += v; if (cl.indexOf(i) >= 0 && cl.indexOf(j) >= 0) inC += v;
      }); });
      $("err-share-final").textContent = (100 * inC / tot).toFixed(0) + "% (" + FL.int(inC) + " of " + FL.int(tot) + " remaining errors)";
    })();

    // ---- training-time bars ----
    (function () {
      var b = D.summary.boosting.train_seconds, d = D.summary.dl_classifier.train_seconds, mx = Math.max(b, d);
      function row(label, v, cls, note) {
        return '<div class="bar-row"><span class="bar-label" style="width:130px">' + label + '</span><div class="bar-track"><div class="bar-fill ' + cls + '" style="width:' + (v / mx * 100).toFixed(1) + '%"></div></div><span class="bar-val" style="width:150px">' + v.toFixed(1) + " s &middot; " + note + "</span></div>";
      }
      $("train-bars").innerHTML = row("Boosting", b, "boost", (b / d).toFixed(1) + "&times; slower") + row("DL classifier", d, "dl", "baseline");
    })();

    // ---- F1 budget ----
    (function () {
      var rows = D.classNames.map(function (c) { return { c: c, f1: byStage.boost[c].f1 }; });
      var sum = rows.reduce(function (a, r) { return a + r.f1; }, 0);
      $("f1-sum").textContent = sum.toFixed(2) + " (= " + (sum / 15).toFixed(3) + " × 15)";
      $("f1-need").textContent = (14.25 - sum).toFixed(2);
      rows.sort(function (a, b) { return a.f1 - b.f1; });
      var h = "";
      rows.forEach(function (r) {
        var gap = Math.max(0, 0.95 - r.f1);
        h += '<div class="budget-row"><span>' + r.c + '</span><div class="budget-track"><div class="budget-fill" style="width:' + (r.f1 * 100).toFixed(1) + '%"></div>' +
          (gap > 0 ? '<div class="budget-gap" style="left:' + (r.f1 * 100).toFixed(1) + '%;width:' + (gap * 100).toFixed(1) + '%"></div>' : "") +
          '</div><span class="budget-val">F1 ' + r.f1.toFixed(3) + (gap > 0 ? " &middot; &minus;" + gap.toFixed(3) : " &middot; ok") + "</span></div>";
      });
      $("f1-budget").innerHTML = h;
    })();

    // ---- accuracy: before / after table ----
    (function () {
      var steps = [
        ["Original 91 features", "base"], ["+ service port (92)", "base_svc"], ["+ content (110)", "base_content"],
        ["+ flow (130)", "full"], ["+ class weights (final)", "full_bal"]
      ];
      var R = ACC.runs;
      function cell(name, k) { var r = R[name]; return r ? (k === "accuracy" ? (r[k] * 100).toFixed(2) + "%" : r[k].toFixed(4)) : "&mdash;"; }
      var h = '<div class="table-wrap"><table class="ptable"><thead><tr><th>Features</th><th>Random: accuracy</th><th>Random: macro F1</th><th>Flow-grouped: accuracy</th><th>Flow-grouped: macro F1</th></tr></thead><tbody>';
      steps.forEach(function (st, i) {
        var g = st[1].replace("_bal", "") + "_grouped" + (st[1].indexOf("_bal") > 0 ? "_bal" : "") + "_s42";
        var last = i === steps.length - 1;
        var tdo = last ? "<td><b>" : "<td>", tdc = last ? "</b></td>" : "</td>";
        h += "<tr>" + tdo + st[0] + tdc + tdo + cell(st[1] + "_s42", "accuracy") + tdc + tdo + cell(st[1] + "_s42", "macro_f1") + tdc +
          tdo + cell(g, "accuracy") + tdc + tdo + cell(g, "macro_f1") + tdc + "</tr>";
      });
      h += "</tbody></table></div>";
      h += '<p class="src">All rows after de-duplication (1,909,719 with the original features; 1,985,768 with all 130), natural class distribution, seed 42. Final configuration across seeds 42/43/44 &mdash; flow-grouped macro F1 ' +
        ["42", "43", "44"].map(function (sd) { return R["full_grouped_bal_s" + sd].macro_f1.toFixed(3); }).join(" / ") +
        "; random " + ["42", "43", "44"].map(function (sd) { return R["full_bal_s" + sd].macro_f1.toFixed(3); }).join(" / ") + ".</p>";
      $("acc-progress").innerHTML = h;
    })();

    // ---- accuracy: per-class F1 before / after (flow-grouped) ----
    (function () {
      var b = ACC.base.perClass, f = ACC.final.perClass;
      var classes = ACC.final.classes.filter(function (c) { return f[c].support > 0 && b[c] && b[c].support > 0; });
      classes.sort(function (x, y) { return (f[y]["f1-score"] - b[y]["f1-score"]) - (f[x]["f1-score"] - b[x]["f1-score"]); });
      var el = $("acc-perclass");
      classes.forEach(function (c) {
        var bo = b[c]["f1-score"], fo = f[c]["f1-score"];
        var w = document.createElement("div"); w.className = "bar-metric";
        w.innerHTML = '<div class="metric-name">' + c + '</div>' +
          '<div class="bar-row"><span class="bar-label">Before</span><div class="bar-track"><div class="bar-fill boost" style="width:' + (bo * 100).toFixed(1) + '%"></div></div><span class="bar-val">' + bo.toFixed(3) + '</span></div>' +
          '<div class="bar-row"><span class="bar-label">Final</span><div class="bar-track"><div class="bar-fill dl" style="width:' + (fo * 100).toFixed(1) + '%"></div></div><span class="bar-val">' + fo.toFixed(3) + '</span></div>';
        el.appendChild(w);
      });
    })();

    // ---- sweep chart ----
    (function () {
      var el = $("sweep-chart"), W = 900, H = 300, pl = 44, pr = 20, pt = 20, pb = 36, pw = W - pl - pr, ph = H - pt - pb;
      function x(f) { return pl + (f / 0.5) * pw; }
      function y(v) { return pt + (1 - v) * ph; }
      var series = [
        { k: "attack_macro_recall", c: "var(--series-boost)", l: "Attack macro-recall" },
        { k: "zero_day_macro_recall", c: "var(--series-dl)", l: "Zero-day macro-recall" },
        { k: "autoencoder_alone_attack_macro_recall", c: "#1baf7a", l: "AE-alone macro-recall" }
      ];
      var s = '<svg viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg" style="font-family:inherit;width:100%;height:auto">';
      [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
        s += '<line x1="' + pl + '" x2="' + (W - pr) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="var(--border)"/><text x="' + (pl - 8) + '" y="' + (y(v) + 4) + '" text-anchor="end" font-size="11" fill="var(--text-muted)">' + v.toFixed(2) + "</text>";
      });
      D.sweep.forEach(function (p) { s += '<text x="' + x(p.malicious_fraction) + '" y="' + (H - 12) + '" text-anchor="middle" font-size="11" fill="var(--text-muted)">' + Math.round(p.malicious_fraction * 100) + "%</text>"; });
      series.forEach(function (se) {
        s += '<polyline points="' + D.sweep.map(function (p) { return x(p.malicious_fraction) + "," + y(p[se.k]); }).join(" ") + '" fill="none" stroke="' + se.c + '" stroke-width="2.5" stroke-linejoin="round"/>';
        D.sweep.forEach(function (p) { s += '<circle cx="' + x(p.malicious_fraction) + '" cy="' + y(p[se.k]) + '" r="4.5" fill="' + se.c + '"><title>' + se.l + " @ " + Math.round(p.malicious_fraction * 100) + "% malicious: " + p[se.k].toFixed(3) + "</title></circle>"; });
      });
      s += "</svg>";
      var lg = '<div class="legend" style="margin-top:10px">' + series.map(function (se) { return '<span><span class="dot" style="background:' + se.c + '"></span>' + se.l + "</span>"; }).join("") + "</div>";
      el.innerHTML = s + lg + '<p class="meta" style="margin-top:8px">x-axis: fraction of clients running a sign-flip poisoning attack. AE-alone and zero-day recall collapse together at 50% &mdash; the trust filter\'s documented breaking point.</p>';
    })();

    // ---- pipeline diagrams ----
    FL.diagram($("diagram-a"), {
      id: "a", aria: "Phase A training pipeline",
      nodes: [
        { id: "n1", col: 0, row: 0, cls: "data", title: "1 · Raw dataset", lines: ["Edge-IIoTset CSV", "2,219,216 rows × 63 columns", "15 attack / normal classes"] },
        { id: "n2", col: 1, row: 0, cls: "data", title: "2 · Clean & encode", lines: ["drop 16 ID/payload columns", "fix label-leak placeholder", "dedupe · repair MITM rows", "one-hot → 1,909,719 × 91"] },
        { id: "n3", col: 2, row: 0, cls: "data", title: "3 · Split", lines: ["Server calibration set: 5%", "(stratified, labelled)", "Federated pool: the rest,", "subsampled to 60,000 rows"] },
        { id: "n4", col: 3, row: 0, cls: "model", title: "4 · Boosting bootstrap", lines: ["LightGBM on raw features", "300 rounds · lr 0.05 · 31 leaves", "trained BEFORE round 1", "held-out accuracy 0.963"] },
        { id: "n5", col: 2, row: 1, cls: "fed", title: "5 · Non-IID partition", lines: ["Dirichlet α=0.3 → 10 clients", "per client: 15% test,", "15% benign val, rest train", "z-score per client, clip ±10"] },
        { id: "n6", col: 3, row: 1, cls: "fed", title: "6 · Client round (×10)", lines: ["boosting filters traffic", "(confident attacks skipped)", "train autoencoder on the rest", "91→32→16→8 · 5 epochs · MSE"] },
        { id: "n7", col: 3, row: 2, cls: "robust", title: "7 · Server aggregation", lines: ["Δ = new − old weights", "cosine / MAD / norm trust filter", "trimmed mean (15%) → global AE", "repeated for 20 rounds"] },
        { id: "n8", col: 3, row: 3, cls: "model", title: "8 · Boosting update", lines: ["every 3 rounds: ≤50 confirmed", "alerts per surviving client", "+50 trees (or retrain)", "→ rebroadcast to clients"] },
        { id: "n9", col: 2, row: 2, cls: "out", title: "9 · Phase A bundle", lines: ["boosting model + AE weights", "per-client scaler & threshold", "manifest + provenance", "→ saved_models/phase_a"] }
      ],
      edges: [
        { from: "n1", to: "n2", label: "63 cols" },
        { from: "n2", to: "n3", label: "1.91M × 91" },
        { from: "n3", to: "n4", label: "labelled" },
        { from: "n3", to: "n5", mode: "v", label: "pool → 60k" },
        { from: "n5", to: "n6", label: "clients" },
        { from: "n4", to: "n6", mode: "v", label: "model broadcast" },
        { from: "n6", to: "n7", mode: "v", label: "Δ weights + alerts" },
        { from: "n7", to: "n6", mode: "loop", label: "new global AE ×20" },
        { from: "n7", to: "n9", label: "round 20" },
        { from: "n7", to: "n8", mode: "v", label: "alerts" }
      ]
    });

    FL.diagram($("diagram-b"), {
      id: "b", aria: "Phase B inference and enforcement pipeline",
      nodes: [
        { id: "b1", col: 0, row: 0, cls: "data", title: "1 · Captured traffic", lines: ["real .pcap, e.g.", "Backdoor_attack.pcap", "24,914 packets"] },
        { id: "b2", col: 1, row: 0, cls: "net", title: "2 · Mininet replay", lines: ["10 hosts · 1 OVS switch", "os-ken OpenFlow 1.3 controller", "tcpreplay from host h1"] },
        { id: "b3", col: 2, row: 0, cls: "data", title: "3 · tshark features", lines: ["46 fields per packet, mapped", "to the authors' spelling", "one-hot encode like training"] },
        { id: "b4", col: 3, row: 0, cls: "out", title: "4 · Load Phase A bundle", lines: ["boosting model, AE weights", "h1 = client 0: its scaler", "and its anomaly threshold"] },
        { id: "b5", col: 3, row: 1, cls: "model", title: "5 · Boosting stage", lines: ["class + probability per packet", "attack and ≥ 0.7 → final label", "is that attack type"] },
        { id: "b6", col: 2, row: 1, cls: "fed", title: "6 · Autoencoder stage", lines: ["otherwise: reconstruction error", "> client threshold → anomalous", "else → benign"] },
        { id: "b7", col: 2, row: 2, cls: "robust", title: "7 · Device verdict", lines: ["most frequent non-benign label", "mean confidence", "+ which stage decided most"] },
        { id: "b8", col: 1, row: 2, cls: "net", title: "8 · Mitigation bridge", lines: ["REST: device, class,", "confidence, stage", "≥0.85 block · ≥0.5 rate-limit", "else allow / monitor"] },
        { id: "b9", col: 0, row: 2, cls: "out", title: "9 · Switch flow table", lines: ["flow-mod via the controller:", "drop rule or meter", "verified with ovs-ofctl", "dump-flows"] }
      ],
      edges: [
        { from: "b1", to: "b2", label: "replay" },
        { from: "b2", to: "b3", label: "packets" },
        { from: "b3", to: "b4", label: "rows" },
        { from: "b4", to: "b5", mode: "v", label: "models" },
        { from: "b5", to: "b6", label: "otherwise" },
        { from: "b6", to: "b7", mode: "v", label: "anomalous / benign" },
        { from: "b5", to: "b7", mode: "vh", label: "confident attack" },
        { from: "b7", to: "b8", label: "verdict" },
        { from: "b8", to: "b9", label: "flow-mod" }
      ]
    });
  });
})();
