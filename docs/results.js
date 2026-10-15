(function () {
  "use strict";
  var D = window.FLIDS, FL = window.FLCommon;
  function $(id) { return document.getElementById(id); }
  function best(rows, key, dir) {          // dir: 1 = max is best, -1 = min is best
    var v = rows.map(function (r) { return r[key]; }).filter(function (x) { return typeof x === "number"; });
    return dir === 1 ? Math.max.apply(null, v) : Math.min.apply(null, v);
  }
  function hl(rows, key, dir) { var b = best(rows, key, dir); return function (v) { return v === b ? "hl" : ""; }; }

  document.addEventListener("DOMContentLoaded", function () {

    // 1 · comparison
    (function () {
      var b = D.summary.boosting, d = D.summary.dl_classifier;
      var rows = [
        { m: "Accuracy", b: b.accuracy, d: d.accuracy, dir: 1, f: 4 },
        { m: "Macro F1", b: b.macro_f1, d: d.macro_f1, dir: 1, f: 4 },
        { m: "Weighted F1", b: b.weighted_f1, d: d.weighted_f1, dir: 1, f: 4 },
        { m: "Benign FPR (lower is better)", b: b.benign_fpr, d: d.benign_fpr, dir: -1, f: 4 },
        { m: "Train time (s)", b: b.train_seconds, d: d.train_seconds, dir: -1, f: 1 }
      ];
      FL.table($("t-compare-head"), [
        { key: "m", label: "Metric" },
        { key: "b", label: "Boosting", fmt: function (v, r) { return v.toFixed(r.f); }, cls: function (v, r) { return (r.dir === 1 ? v >= r.d : v <= r.d) ? "hl" : ""; } },
        { key: "d", label: "DL classifier", fmt: function (v, r) { return v.toFixed(r.f); }, cls: function (v, r) { return (r.dir === 1 ? v > r.b : v < r.b) ? "hl" : ""; } }
      ], rows, { cls: "dense" });

      var by = {};
      D.perClassCompare.forEach(function (r) { by[r["class"]] = by[r["class"]] || {}; by[r["class"]][r.stage === "boosting_alone" ? "b" : "d"] = r; });
      var cr = D.classNames.map(function (c) { return { c: c, b: by[c].b, d: by[c].d, support: by[c].b.support }; });
      var lo = function (v) { return v < 0.5 ? "lo" : ""; };
      FL.table($("t-compare-class"), [
        { key: "c", label: "Class" },
        { get: function (r) { return r.support; }, label: "Test rows", fmt: FL.int },
        { get: function (r) { return r.b.precision; }, label: "Boost prec.", fmt: FL.f3 },
        { get: function (r) { return r.b.recall; }, label: "Boost recall", fmt: FL.f3, cls: lo },
        { get: function (r) { return r.b.f1; }, label: "Boost F1", fmt: FL.f3 },
        { get: function (r) { return r.d.precision; }, label: "DL prec.", fmt: FL.f3 },
        { get: function (r) { return r.d.recall; }, label: "DL recall", fmt: FL.f3, cls: lo },
        { get: function (r) { return r.d.f1; }, label: "DL F1", fmt: FL.f3 },
        { get: function (r) { return r.b.f1 - r.d.f1; }, label: "F1 gap", fmt: function (v) { return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(3); }, cls: function (v) { return v > 0.3 ? "hl" : ""; } }
      ], cr, { cls: "dense" });
    })();

    // 2-6 · federated results; rendered for the current pipeline and for the original 91 features
    function renderFederated(S, P) {
      // 2 · stage report
      (function () {
        var bo = S.stageReport.filter(function (r) { return r.stage === "boosting_alone"; });
        var lo = function (v) { return v < 0.8 ? "lo" : ""; };
        FL.table($(P + "t-stage-boost"), [
          { key: "class", label: "Class" }, { key: "support", label: "Test rows", fmt: FL.int },
          { key: "precision", label: "Precision", fmt: FL.f3, cls: lo }, { key: "recall", label: "Recall", fmt: FL.f3, cls: lo },
          { key: "f1", label: "F1", fmt: FL.f3, cls: lo }, { key: "auroc", label: "AUROC", fmt: FL.f4 }
        ], bo, { cls: "dense" });
        var bi = S.stageReport.filter(function (r) { return r.stage !== "boosting_alone"; });
        FL.table($(P + "t-stage-binary"), [
          { key: "stage", label: "Stage" }, { key: "class", label: "Class" }, { key: "support", label: "Rows", fmt: FL.int },
          { key: "precision", label: "Precision", fmt: FL.f3 }, { key: "recall", label: "Recall", fmt: FL.f3 }, { key: "f1", label: "F1", fmt: FL.f3 },
          { key: "auroc", label: "AUROC", fmt: FL.f4 }, { key: "stage_accuracy", label: "Stage accuracy", fmt: FL.f4 }, { key: "stage_false_positive_rate", label: "Benign FPR", fmt: FL.f4 }
        ], bi, { cls: "dense" });
      })();

      // 3 · ablation
      (function () {
        var rows = S.ablation;
        FL.table($(P + "t-ablation"), [
          { key: "variant", label: "Variant" },
          { key: "attack_macro_recall", label: "Attack macro-recall", fmt: FL.f3, cls: hl(rows, "attack_macro_recall", 1) },
          { key: "benign_fpr", label: "Benign FPR", fmt: FL.f4, cls: hl(rows, "benign_fpr", -1) },
          { key: "detection_f1", label: "Detection F1", fmt: FL.f3, cls: hl(rows, "detection_f1", 1) },
          { key: "zero_day_macro_recall", label: "Zero-day macro-recall", fmt: FL.f3, cls: hl(rows, "zero_day_macro_recall", 1) },
          { key: "autoencoder_alone_attack_macro_recall", label: "AE-alone recall", fmt: FL.f3, cls: hl(rows, "autoencoder_alone_attack_macro_recall", 1) },
          { key: "final_val_loss", label: "Final val loss", fmt: FL.sci },
          { key: "rounds_to_convergence", label: "Rounds to converge", fmt: function (v) { return v === null ? "diverged / n/a" : v; } },
          { key: "total_communication_bytes", label: "Comm. bytes", fmt: FL.int }
        ], rows, { cls: "dense" });

        var variants = S.ablation.map(function (r) { return r.variant; });
        var by = {};
        S.ablationPerClass.forEach(function (r) { by[r.attack_type] = by[r.attack_type] || {}; by[r.attack_type][r.variant] = r.recall; });
        var cls = Object.keys(by).sort().map(function (k) { var o = { c: k }; variants.forEach(function (v) { o[v] = by[k][v]; }); return o; });
        var cols = [{ key: "c", label: "Attack type" }].concat(variants.map(function (v) {
          return { key: v, label: v, fmt: FL.f3, cls: function (x) { return x < 0.3 ? "lo" : ""; } };
        }));
        FL.table($(P + "t-ablation-class"), cols, cls, { cls: "dense" });
      })();

      // 4 · sweep
      FL.table($(P + "t-sweep"), [
        { get: function (r) { return Math.round(r.malicious_fraction * 100) + "%"; }, label: "Malicious" },
        { key: "attack_macro_recall", label: "Attack macro-recall", fmt: FL.f3 },
        { key: "benign_fpr", label: "Benign FPR", fmt: FL.f4 },
        { key: "detection_f1", label: "Detection F1", fmt: FL.f3 },
        { key: "zero_day_macro_recall", label: "Zero-day macro-recall", fmt: FL.f3, cls: function (v) { return v < 0.65 ? "lo" : ""; } },
        { key: "autoencoder_alone_attack_macro_recall", label: "AE-alone recall", fmt: FL.f3, cls: function (v) { return v === 0 ? "lo" : ""; } },
        { key: "malicious_client_survival_rate", label: "Attacker survival", fmt: FL.f3, cls: function (v) { return v > 0.9 ? "lo" : ""; } },
        { key: "final_val_loss", label: "Final val loss", fmt: FL.sci },
        { key: "rounds_to_convergence", label: "Rounds to converge", fmt: function (v) { return v === null ? "diverged" : v; } }
      ], S.sweep, { cls: "dense" });

      // 5 · multiseed
      (function () {
        var rows = [];
        S.sweep.forEach(function (r) { if (r.malicious_fraction === 0.2 || r.malicious_fraction === 0.3) rows.push({ seed: 42, f: r.malicious_fraction, rec: r.attack_macro_recall, fpr: r.benign_fpr, ae: r.autoencoder_alone_attack_macro_recall }); });
        S.multiseed.forEach(function (r) { rows.push({ seed: r.seed, f: r.malicious_fraction, rec: r.attack_macro_recall, fpr: r.benign_fpr, ae: r.autoencoder_alone_attack_macro_recall }); });
        rows.sort(function (a, b) { return a.seed - b.seed || a.f - b.f; });
        FL.table($(P + "t-multiseed"), [
          { key: "seed", label: "Seed" }, { get: function (r) { return Math.round(r.f * 100) + "%"; }, label: "Malicious" },
          { key: "rec", label: "Attack macro-recall", fmt: FL.f3 }, { key: "fpr", label: "Benign FPR", fmt: FL.f4 }, { key: "ae", label: "AE-alone recall", fmt: FL.f3 }
        ], rows, { cls: "dense" });
      })();

      // 6 · zero-day
      (function () {
        var rows = S.zeroDay;
        FL.table($(P + "t-zeroday"), [
          { key: "holdout_class", label: "Held-out class" }, { key: "holdout_rows", label: "Rows", fmt: FL.int },
          { key: "boosting_only_detection_rate", label: "Boosting-only", fmt: FL.f3, cls: function (v) { return v < 0.2 ? "lo" : ""; } },
          { key: "autoencoder_alone_detection_rate", label: "AE-alone", fmt: FL.f3 },
          { key: "cascade_detection_rate", label: "Cascade", fmt: FL.f3, cls: hl(rows, "cascade_detection_rate", 1) },
          { key: "autoencoder_added_detection_rate", label: "AE added", fmt: FL.f3, cls: function (v) { return v > 0.5 ? "hl" : ""; } },
          { get: function (r) { return r.boosting_top_misattributed_label ? r.boosting_top_misattributed_label + " (" + (r.boosting_top_misattributed_share * 100).toFixed(0) + "%)" : "—"; }, label: "Boosting's top misattribution" },
          { key: "autoencoder_auroc_vs_benign", label: "AE AUROC", fmt: FL.f3 },
          { key: "cascade_benign_fpr", label: "Cascade FPR", fmt: FL.f4 }
        ], rows, { cls: "dense" });
      })();
    }
    renderFederated(D, "");
    renderFederated(D.base, "b-");

    // 8 · classifier accuracy
    (function () {
      var R = D.accuracy.runs;
      var label = { base: "Original 91", base_svc: "+ service port", base_content: "+ content", full: "+ flow (130)" };
      var rows = Object.keys(R).map(function (k) {
        var r = R[k], extra = [];
        if (r.balanced_weights) extra.push("class weights");
        if (r.sample) extra.push(FL.int(r.sample) + "-row sample");
        if (r.train_fraction) extra.push("trained on " + (r.train_fraction * 100) + "% of rows");
        return { name: k, fs: label[r.feature_set] + (extra.length ? " · " + extra.join(", ") : ""), split: r.split === "flow_grouped" ? "flow-grouped" : "random",
                 seed: r.seed, nf: r.n_features, test: r.test_rows, acc: r.accuracy, f1: r.macro_f1, amb: r.ambiguous_share, ceil: r.ceiling_macro_recall };
      });
      var order = ["base", "base_svc", "base_content", "full"];
      rows.sort(function (a, b) { return order.indexOf(R[a.name].feature_set) - order.indexOf(R[b.name].feature_set) || a.fs.localeCompare(b.fs) || a.split.localeCompare(b.split) || a.seed - b.seed; });
      var tgt = function (v) { return v >= 0.95 ? "hl" : (v < 0.9 ? "lo" : ""); };
      FL.table($("t-acc-runs"), [
        { key: "fs", label: "Features / setting" }, { key: "split", label: "Split" }, { key: "seed", label: "Seed" },
        { key: "nf", label: "Features" }, { key: "test", label: "Test rows", fmt: FL.int },
        { key: "acc", label: "Accuracy", fmt: FL.f4, cls: tgt }, { key: "f1", label: "Macro F1", fmt: FL.f4, cls: tgt },
        { key: "amb", label: "Ambiguous rows", fmt: function (v) { return (v * 100).toFixed(2) + "%"; } },
        { key: "ceil", label: "Ceiling macro recall", fmt: FL.f4 }
      ], rows, { cls: "dense" });

      var f = D.accuracy.final, b = D.accuracy.base;
      var cr = f.classes.filter(function (c) { return f.perClass[c].support > 0; }).map(function (c) {
        var p = f.perClass[c]; return { c: c, n: p.support, p: p.precision, r: p.recall, f1: p["f1-score"], b: b.perClass[c]["f1-score"] };
      });
      FL.table($("t-acc-final"), [
        { key: "c", label: "Class" }, { key: "n", label: "Test rows", fmt: FL.int },
        { key: "p", label: "Precision", fmt: FL.f3 }, { key: "r", label: "Recall", fmt: FL.f3 }, { key: "f1", label: "F1", fmt: FL.f3, cls: tgt },
        { key: "b", label: "F1 with original features", fmt: FL.f3, cls: function (v) { return v < 0.9 ? "lo" : ""; } }
      ], cr, { cls: "dense" });
    })();
  });
})();
