// Shared colours, formatters and Chart.js defaults.
(function () {
  const css = getComputedStyle(document.documentElement);
  const v = n => css.getPropertyValue(n).trim();

  window.C = {
    ink: "#1a1a1a", inkSoft: "#4a4a4a", inkFaint: "#7c7c78",
    line: "#e0ded6", grid: "rgba(0,0,0,.06)",
    green: v("--green") || "#11623e", greenL: v("--green-l") || "#2e8b62",
    gold: v("--gold") || "#c79a3a", goldL: v("--gold-l") || "#e3c878",
    grant: "#2e8b62", refuse: "#c0392b", pending: "#c79a3a",
    nation: { England: "#1d3557", Scotland: "#0f8b8d", Wales: "#c1121f", "Northern Ireland": "#6a4c93", NI: "#6a4c93" },
    party: {
      Con: "#0087dc", Lab: "#e4003b", LibDem: "#faa61a", "Lib Dem": "#faa61a",
      SNP: "#d9bf00", Plaid: "#005b54", Green: "#02a95b", Reform: "#12b6cf",
      "Other/Ind": "#9b9b9b", "Nationalist (pre-2007)": "#7a6f9b",
    },
    // grey ramp for technologies (renewables get colour where it matters)
    tech: {
      "Solar Photovoltaics": "#e3a72f", Solar: "#e3a72f",
      "Wind Onshore": "#2e7fb8", OnshoreWind: "#2e7fb8",
      "Wind Offshore": "#1d3557", OffshoreWind: "#1d3557",
      Battery: "#6a4c93",
    },
  };

  // Number helpers
  window.fmt = {
    n: x => (x == null ? "—" : Number(x).toLocaleString("en-GB")),
    gw: mw => (mw == null ? "—" : (mw / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })),
    pct: x => (x == null ? "—" : Number(x).toFixed(1) + "%"),
  };

  if (window.Chart) {
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.font.size = 12.5;
    Chart.defaults.color = C.inkSoft;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.legend.labels.padding = 16;
    Chart.defaults.plugins.tooltip.backgroundColor = "#1a1a1a";
    Chart.defaults.plugins.tooltip.padding = 11;
    Chart.defaults.plugins.tooltip.cornerRadius = 6;
    Chart.defaults.plugins.tooltip.titleFont = { weight: "600" };
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation.duration = 600;
  }

  // grid/axis styling shortcut
  window.axis = (opts = {}) => ({
    grid: { color: C.grid, drawTicks: false },
    border: { display: false },
    ticks: { padding: 8, ...(opts.ticks || {}) },
    ...opts,
  });
})();
