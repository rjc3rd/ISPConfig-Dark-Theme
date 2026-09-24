/* Chart.js defaults for the dark theme. Charts draw on <canvas>, which CSS
 * can't restyle, so text, grid and legend colors are set here before the
 * dashboard/monitor dashlets create their charts. */
(function () {
  if (typeof Chart === 'undefined') return;
  Chart.defaults.color = '#c3c3c3';
  Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
  // The metrics dashlet paints its legend swatch white (meant to vanish on
  // the old white canvas); drop the swatch instead.
  Chart.defaults.plugins.legend.labels.boxWidth = 0;
})();
