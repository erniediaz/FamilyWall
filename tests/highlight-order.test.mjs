import {test} from 'node:test';
import assert from 'node:assert/strict';
import {highlightOrder, HIGHLIGHT_INTERVAL} from '../lib/highlight-order.ts';
const item = (id, category) => ({id, category, text: id, detail: '', source: '', url: ''});
test('every category gets a turn even with many sports scores', () => {
  const rows = [item('h', 'history'), item('o', 'observances'), item('q', 'quotes'), ...Array.from({length: 30}, (_, i) => item('s' + i, 'sports'))];
  const order = highlightOrder(rows, () => .5);
  for (let i = 0; i < order.length; i += 4) {
    assert.equal(new Set(order.slice(i, i + 4).map(id => rows.find(row => row.id === id).category)).size, 4);
  }
  assert.equal(new Set(order.filter(id => id.startsWith('s'))).size, 30);
  assert.equal(HIGHLIGHT_INTERVAL, 15000);
});
test('empty, single category, and duplicate items are safe', () => {
  assert.deepEqual(highlightOrder([]), []);
  assert.deepEqual(highlightOrder([item('h', 'history'), item('h', 'history')]), ['h']);
});
test('three active teams cycle through one sports slot per four-card round', () => {
  const rows = ['history', 'observances', 'quotes'].flatMap(category => Array.from({length:10}, (_,i) => item(category+i, category)));
  rows.push(...['broncos','rockies','gators'].map(id => item(id, 'sports')));
  const order = highlightOrder(rows, () => .5);
  const sports = order.filter(id => ['broncos','rockies','gators'].includes(id));
  assert.equal(order.length, 40);
  assert.equal(sports.length, 10);
  for (let i=0; i<9; i+=3) assert.equal(new Set(sports.slice(i,i+3)).size,3);
});
test('all unique items appear and inputs remain intact', () => {
  const rows = Array.from({length: 10}, (_, i) => item('q' + i, 'quotes'));
  const original = structuredClone(rows);
  const order = highlightOrder(rows, () => 0);
  assert.equal(new Set(order).size, 10);
  assert.notDeepEqual(order, rows.map(row => row.id));
  assert.deepEqual(rows, original);
});
