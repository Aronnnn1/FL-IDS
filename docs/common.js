(function () {
  "use strict";
  var root = document.documentElement;
  var listeners = [];
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function effectiveIsDark() {
    var t = root.getAttribute("data-theme");
    if (t) return t === "dark";
    return !!(mq && mq.matches);
  }
  function applyTheme(t) {
    if (t) root.setAttribute("data-theme", t); else root.removeAttribute("data-theme");
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = effectiveIsDark() ? "Light mode" : "Dark mode";
    listeners.forEach(function (cb) { cb(effectiveIsDark()); });
  }
  var FL = window.FLCommon = {
    isDark: effectiveIsDark,
    onTheme: function (cb) { listeners.push(cb); },
  };
  document.addEventListener("DOMContentLoaded", function () {
    try { var s = localStorage.getItem("fl-ids-theme"); if (s) applyTheme(s); else applyTheme(null); } catch (e) { applyTheme(null); }
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.addEventListener("click", function () {
      var next = effectiveIsDark() ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem("fl-ids-theme", next); } catch (e) {}
    });
  });

  /* ---------- number formatting ---------- */
  FL.f = function (d) { return function (v) { return v === null || v === undefined || v === "" ? "—" : (typeof v === "number" ? v.toFixed(d) : v); }; };
  FL.f2 = FL.f(2); FL.f3 = FL.f(3); FL.f4 = FL.f(4);
  FL.int = function (v) { return v === null || v === undefined ? "—" : Number(v).toLocaleString("en-US"); };
  FL.sci = function (v) { return v === null || v === undefined ? "—" : (Math.abs(v) >= 1e4 || (v !== 0 && Math.abs(v) < 1e-3) ? v.toExponential(2) : v.toFixed(4)); };

  /* ---------- generic table ---------- */
  // cols: [{key|get, label, fmt, cls(value,row)->string}]
  FL.table = function (el, cols, rows, opts) {
    opts = opts || {};
    var h = '<div class="table-wrap"><table class="' + (opts.cls || "") + '"><thead><tr>';
    cols.forEach(function (c) { h += "<th>" + c.label + "</th>"; });
    h += "</tr></thead><tbody>";
    rows.forEach(function (r) {
      h += "<tr>";
      cols.forEach(function (c) {
        var v = c.get ? c.get(r) : r[c.key];
        var s = c.fmt ? c.fmt(v, r) : (v === null || v === undefined ? "—" : v);
        var k = c.cls ? c.cls(v, r) : "";
        h += '<td class="' + (k || "") + '">' + s + "</td>";
      });
      h += "</tr>";
    });
    h += "</tbody></table></div>";
    el.innerHTML = h;
  };

  /* ---------- heatmap (confusion matrix) ---------- */
  var LIGHT = [[0, [250, 250, 248]], [0.15, [205, 226, 251]], [0.4, [109, 167, 236]], [0.7, [37, 106, 191]], [1, [13, 54, 107]]];
  var DARK = [[0, [38, 38, 34]], [0.15, [30, 56, 92]], [0.4, [28, 88, 160]], [0.7, [57, 135, 229]], [1, [170, 208, 248]]];
  function ramp(t, dark) {
    var s = dark ? DARK : LIGHT;
    for (var i = 0; i < s.length - 1; i++) {
      var a = s[i], b = s[i + 1];
      if (t <= b[0]) {
        var u = (t - a[0]) / (b[0] - a[0] || 1);
        return [0, 1, 2].map(function (k) { return Math.round(a[1][k] + (b[1][k] - a[1][k]) * u); });
      }
    }
    return s[s.length - 1][1];
  }
  function lum(rgb) { return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]; }
  function css(rgb) { return "rgb(" + rgb.join(",") + ")"; }

  FL.heatScaleCss = function () {
    var dark = effectiveIsDark();
    var stops = [0, 0.15, 0.4, 0.7, 1].map(function (t) { return css(ramp(t, dark)) + " " + (t * 100) + "%"; });
    return "linear-gradient(90deg," + stops.join(",") + ")";
  };

  // mode: "count" | "pct". Colour always encodes row fraction (diagonal = recall).
  FL.heatmap = function (container, matrix, labels, mode) {
    var dark = effectiveIsDark();
    container.innerHTML = "";
    var table = document.createElement("table");
    table.className = "cm-table";
    var thead = document.createElement("thead"), hr = document.createElement("tr");
    hr.appendChild(document.createElement("th"));
    labels.forEach(function (l) {
      var th = document.createElement("th"); th.className = "colhead";
      var sp = document.createElement("span"); sp.textContent = l; th.appendChild(sp); hr.appendChild(th);
    });
    thead.appendChild(hr); table.appendChild(thead);
    var tb = document.createElement("tbody");
    matrix.forEach(function (row, i) {
      var sum = row.reduce(function (a, b) { return a + b; }, 0) || 1;
      var tr = document.createElement("tr");
      var rh = document.createElement("th"); rh.className = "rowhead"; rh.textContent = labels[i]; tr.appendChild(rh);
      row.forEach(function (count, j) {
        var frac = count / sum;
        var rgb = ramp(Math.pow(frac, 0.5), dark);
        var td = document.createElement("td");
        td.style.background = css(rgb);
        if (i === j) td.className = "diag";
        var txt = lum(rgb) > 150 ? "#0b0b0b" : "#ffffff";
        var shown = "";
        if (count > 0) shown = mode === "pct" ? (frac * 100 >= 10 ? Math.round(frac * 100) : (frac * 100).toFixed(1)) : count;
        td.innerHTML = '<span class="cm-cell-val" style="color:' + txt + '">' + shown + "</span>";
        td.title = labels[i] + " → predicted " + labels[j] + ": " + count.toLocaleString() + " rows (" + (frac * 100).toFixed(1) + "% of true " + labels[i] + ")";
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    table.appendChild(tb); container.appendChild(table);
  };

  /* ---------- pipeline diagram ---------- */
  // spec: {id, nodes:[{id,col,row,title,lines,cls}], edges:[{from,to,label,mode}]}
  FL.diagram = function (el, spec) {
    var NW = 212, NH = 104, GX = 268, GY = 140, PX = 14, PY = 14;
    var rows = Math.max.apply(null, spec.nodes.map(function (n) { return n.row; })) + 1;
    var VW = 1090, VH = PY * 2 + (rows - 1) * GY + NH;
    var N = {};
    spec.nodes.forEach(function (n) {
      n.x = PX + n.col * GX; n.y = PY + n.row * GY; n.cx = n.x + NW / 2; n.cy = n.y + NH / 2; N[n.id] = n;
    });
    var s = '<svg viewBox="0 0 ' + VW + " " + VH + '" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="' + (spec.aria || "pipeline diagram") + '">';
    s += '<defs><marker id="arr-' + spec.id + '" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" class="dg-arrow"/></marker></defs>';
    var labels = "";
    spec.edges.forEach(function (e) {
      var a = N[e.from], b = N[e.to], d, lx, ly, anchor = "middle";
      var m = e.mode || "h";
      if (m === "h") {
        var right = b.col > a.col;
        var x1 = right ? a.x + NW : a.x, x2 = right ? b.x : b.x + NW;
        d = "M" + x1 + " " + a.cy + " H" + x2; lx = (x1 + x2) / 2; ly = a.cy - 8;
      } else if (m === "v") {
        var down = b.row > a.row;
        var y1 = down ? a.y + NH : a.y, y2 = down ? b.y : b.y + NH;
        d = "M" + a.cx + " " + y1 + " V" + y2; lx = a.cx + 8; ly = (y1 + y2) / 2 + 4; anchor = "start";
      } else if (m === "vh") {
        var xe = b.col < a.col ? b.x + NW : b.x;
        d = "M" + a.cx + " " + (a.y + NH) + " V" + b.cy + " H" + xe; lx = (a.cx + xe) / 2; ly = b.cy - 8;
      } else if (m === "loop") {
        var xr = a.x + NW, xo = xr + 16;
        d = "M" + xr + " " + a.cy + " H" + xo + " V" + b.cy + " H" + (b.x + NW); lx = xo + 10; ly = (a.cy + b.cy) / 2; anchor = "middle";
      }
      s += '<path class="dg-edge" d="' + d + '" marker-end="url(#arr-' + spec.id + ')"/>';
      if (e.label) {
        if (m === "loop") labels += '<text class="dg-label" text-anchor="middle" transform="translate(' + lx + " " + ly + ') rotate(90)">' + e.label + "</text>";
        else labels += '<text class="dg-label" x="' + lx + '" y="' + ly + '" text-anchor="' + anchor + '">' + e.label + "</text>";
      }
    });
    spec.nodes.forEach(function (n) {
      s += '<rect class="dg-node ' + n.cls + '" x="' + n.x + '" y="' + n.y + '" width="' + NW + '" height="' + NH + '" rx="10"/>';
      s += '<text class="dg-title" x="' + (n.x + 12) + '" y="' + (n.y + 22) + '">' + n.title + "</text>";
      n.lines.forEach(function (ln, i) { s += '<text class="dg-line" x="' + (n.x + 12) + '" y="' + (n.y + 42 + i * 15.5) + '">' + ln + "</text>"; });
    });
    s += labels + "</svg>";
    el.innerHTML = '<div class="dg-wrap">' + s + "</div>";
  };
})();
