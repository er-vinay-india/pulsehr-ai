import assert from 'node:assert/strict';
import * as echarts from 'echarts';
import { cartesian, numeric } from '../src/components/charts/chartOptions.js';
assert.equal(numeric(null), null);
assert.equal(numeric(''), null);
assert.equal(numeric('invalid'), null);
assert.equal(numeric(0), 0);
assert.equal(numeric(-4), -4);
const categories = Array.from({ length: 30 }, (_, i) => `Department ${i}`);
const option = cartesian(categories, [{ type: 'bar', data: categories.map((_,i) => i === 0 ? -4 : i === 1 ? null : i) }], true);
assert.equal(option.yAxis.data.length, 30);
assert.equal(option.series[0].data[0], -4);
assert.equal(option.series[0].data[1], null);
assert.equal(option.dataZoom[0].yAxisIndex, 0);
for (const width of [320, 900]) {
  const chart = echarts.init(null, null, { renderer: 'svg', ssr: true, width, height: 300 });
  chart.setOption(option);
  const svg = chart.renderToSVGString();
  assert.ok(svg.includes('<svg'));
  assert.ok(!svg.includes('NaN'));
  chart.dispose();
}
console.log('Chart data integrity and narrow/wide ECharts render checks passed.');
