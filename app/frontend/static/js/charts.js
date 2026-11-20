/* أدوات الرسوم البيانية (Chart.js) بإعدادات عربية موحّدة */
(function (global) {
  "use strict";

  const registry = {};

  const PALETTE = {
    navy: "#2c5f8a",
    navyLight: "#7aa9c9",
    teal: "#1a7f6b",
    amber: "#b7791f",
    red: "#b83227",
    grey: "#a9b3c0",
  };

  const SERIES = ["#2c5f8a", "#1a7f6b", "#b7791f", "#b83227", "#6a5acd", "#4a7fa8", "#8a6d3b"];

  if (global.Chart) {
    Chart.defaults.font.family = '"IBM Plex Sans Arabic", "Segoe UI", Tahoma, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = "#3c4757";
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.tooltip.rtl = true;
    Chart.defaults.plugins.tooltip.textDirection = "rtl";
  }

  function destroy(id) {
    if (registry[id]) {
      registry[id].destroy();
      delete registry[id];
    }
  }

  function render(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    destroy(id);
    config.options = config.options || {};
    config.options.responsive = true;
    config.options.maintainAspectRatio = false;
    registry[id] = new Chart(canvas.getContext("2d"), config);
    return registry[id];
  }

  function bar(id, labels, values, options) {
    options = options || {};
    return render(id, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: options.label || "العدد",
          data: values,
          backgroundColor: options.colors || PALETTE.navy,
          borderRadius: 5,
          maxBarThickness: options.horizontal ? 22 : 46,
        }],
      },
      options: {
        indexAxis: options.horizontal ? "y" : "x",
        plugins: { legend: { display: !!options.showLegend } },
        scales: {
          x: { grid: { display: !options.horizontal ? false : true, color: "#eef2f7" }, ticks: { autoSkip: false } },
          y: { beginAtZero: true, grid: { color: "#eef2f7" } },
        },
      },
    });
  }

  function groupedBar(id, labels, datasets) {
    return render(id, {
      type: "bar",
      data: {
        labels: labels,
        datasets: datasets.map(function (d, i) {
          return {
            label: d.label,
            data: d.data,
            backgroundColor: d.color || SERIES[i % SERIES.length],
            borderRadius: 5,
            maxBarThickness: 34,
          };
        }),
      },
      options: {
        plugins: { legend: { position: "top", align: "end" } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { color: "#eef2f7" } },
        },
      },
    });
  }

  function doughnut(id, labels, values, colors) {
    return render(id, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{ data: values, backgroundColor: colors || SERIES, borderWidth: 2, borderColor: "#fff" }],
      },
      options: {
        cutout: "58%",
        plugins: { legend: { position: "bottom" } },
      },
    });
  }

  function line(id, labels, values, label) {
    return render(id, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: label || "القيمة",
          data: values,
          borderColor: PALETTE.navy,
          backgroundColor: "rgba(44,95,138,.12)",
          fill: true,
          tension: .32,
          pointRadius: 3,
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, grid: { color: "#eef2f7" } }, x: { grid: { display: false } } },
      },
    });
  }

  function divergingBar(id, labels, values) {
    const colors = values.map(function (v) { return v > 0 ? PALETTE.red : PALETTE.teal; });
    return render(id, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "قيمة SHAP",
          data: values,
          backgroundColor: colors,
          borderRadius: 4,
          maxBarThickness: 20,
        }],
      },
      options: {
        indexAxis: "y",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const v = ctx.raw;
                return (v > 0 ? "يرفع الخطر بمقدار " : "يخفض الخطر بمقدار ") + Math.abs(v).toFixed(3);
              },
            },
          },
        },
        scales: {
          x: { grid: { color: "#eef2f7" }, title: { display: true, text: "قيمة SHAP" } },
          y: { grid: { display: false } },
        },
      },
    });
  }

  function rocChart(id, series) {
    return render(id, {
      type: "line",
      data: {
        datasets: series.map(function (s, i) {
          return {
            label: s.label,
            data: s.fpr.map(function (x, idx) { return { x: x, y: s.tpr[idx] }; }),
            borderColor: SERIES[i % SERIES.length],
            backgroundColor: "transparent",
            pointRadius: 0,
            borderWidth: 2,
            tension: .1,
          };
        }).concat([{
          label: "خط العشوائية",
          data: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
          borderColor: PALETTE.grey,
          borderDash: [6, 5],
          pointRadius: 0,
          borderWidth: 1.4,
        }]),
      },
      options: {
        parsing: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { type: "linear", min: 0, max: 1, title: { display: true, text: "معدل الإيجابيات الخاطئة (FPR)" }, grid: { color: "#eef2f7" } },
          y: { type: "linear", min: 0, max: 1, title: { display: true, text: "معدل الإيجابيات الصحيحة (TPR)" }, grid: { color: "#eef2f7" } },
        },
      },
    });
  }

  global.Charts = {
    render: render, destroy: destroy, bar: bar, groupedBar: groupedBar,
    doughnut: doughnut, line: line, divergingBar: divergingBar, rocChart: rocChart,
    PALETTE: PALETTE, SERIES: SERIES,
  };
})(window);
