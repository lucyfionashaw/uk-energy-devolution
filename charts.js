// Shared colours, formatters and Chart.js defaults.
(function () {
  const css = getComputedStyle(document.documentElement);
  const v = n => css.getPropertyValue(n).trim();

  window.C = {
    ink: "#1a1a1a", inkSoft: "#4a4a4a", inkFaint: "#7c7c78",
    line: "#e0ded6", grid: "rgba(0,0,0,.06)",
    green: v("--green") || "#11623e", greenL: v("--green-l") || "#2e8b62",
    greenD: v("--green-d") || "#0c4a2f",
    gold: v("--gold") || "#c79a3a", goldL: v("--gold-l") || "#e3c878",
    grant: "#2e8b62", refuse: "#c0392b", pending: "#c79a3a",
    nation: { England: "#1d3557", Scotland: "#0f8b8d", Wales: "#c1121f", "Northern Ireland": "#6a4c93", NI: "#6a4c93" },
    party: {
      Con: "#0087dc", Lab: "#e4003b", LibDem: "#d06f00", "Lib Dem": "#d06f00",
      SNP: "#d4b500", Plaid: "#0a8f77", Green: "#02a95b", Reform: "#12b6cf",
      "Sinn Fein": "#326760", DUP: "#b81e26",
      "Other/Ind": "#9b9b9b", "Nationalist (pre-2007)": "#7a6f9b",
    },
    // grey ramp for technologies (renewables get colour where it matters)
    tech: {
      "Solar Photovoltaics": "#dd9c1c", Solar: "#dd9c1c",
      "Wind Onshore": "#2e7fb8", OnshoreWind: "#2e7fb8",
      "Wind Offshore": "#1e3a63", OffshoreWind: "#1e3a63",
      Battery: "#6a4c93",
    },
  };

  // Number helpers
  window.fmt = {
    n: x => (x == null ? "—" : Number(x).toLocaleString("en-GB")),
    gw: mw => (mw == null ? "—" : (mw / 1000).toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 })),
    pct: x => (x == null ? "—" : Number(x).toFixed(1) + "%"),
  };

  if (window.Chart) {
    Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
    Chart.defaults.font.size = 16;
    Chart.defaults.color = "#6e6c66";
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.legend.labels.padding = 16;
    Chart.defaults.plugins.legend.labels.color = C.inkSoft;
    // newsroom tooltip: white card, hairline border, dark text
    Chart.defaults.plugins.tooltip.backgroundColor = "rgba(255,255,255,.97)";
    Chart.defaults.plugins.tooltip.titleColor = C.ink;
    Chart.defaults.plugins.tooltip.bodyColor = C.inkSoft;
    Chart.defaults.plugins.tooltip.borderColor = "rgba(0,0,0,.12)";
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = { x: 13, y: 10 };
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.titleFont = { weight: "700", size: 12.5 };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
    Chart.defaults.plugins.tooltip.boxPadding = 5;
    Chart.defaults.plugins.tooltip.caretSize = 5;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation.duration = 450;
  }

  // grid/axis styling shortcut
  window.axis = (opts = {}) => ({
    grid: { color: "rgba(0,0,0,.055)", drawTicks: false },
    border: { display: false },
    ticks: { padding: 8, font: { size: 16 }, ...(opts.ticks || {}) },
    ...opts,
    ...(opts.title ? { title: { font: { size: 16, weight: "600" }, ...opts.title } } : {}),
  });
})();
