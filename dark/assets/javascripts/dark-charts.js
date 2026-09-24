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
  // Its custom generateLabels() also omits fontColor, and Chart.js 4 draws
  // legend text with the item's fontColor (black when unset). Fill it in
  // after the built-in legend plugin has built its items.
  Chart.register({
    id: 'darkLegendText',
    afterUpdate: function (chart) {
      var items = chart.legend && chart.legend.legendItems;
      if (!items) return;
      items.forEach(function (item) {
        if (!item.fontColor) item.fontColor = Chart.defaults.color;
      });
    }
  });
})();
