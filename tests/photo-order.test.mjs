import { test } from 'node:test';
import assert from 'node:assert/strict';
import { photoOrder } from '../lib/photo-order.ts';

test('startup shuffles every photo exactly once without changing input', () => {
  const photos = ['a', 'b', 'c', 'd'];
  const result = photoOrder(photos, [], () => 0);
  assert.notDeepEqual(result, photos);
  assert.deepEqual([...result].sort(), photos);
  assert.deepEqual(photos, ['a', 'b', 'c', 'd']);
});
test('polling preserves order even when server ordering changes', () => {
  assert.deepEqual(photoOrder(['b', 'a', 'c'], ['c', 'a', 'b']), ['c', 'a', 'b']);
});
test('album changes remove missing photos and append new ones once', () => {
  const result = photoOrder(['b', 'c', 'd', 'd'], ['a', 'c', 'b'], () => 0);
  assert.deepEqual(result, ['c', 'b', 'd']);
  assert.deepEqual(photoOrder([]), []);
  assert.deepEqual(photoOrder(['a']), ['a']);
});
