import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { budgetCheck, chooseThreshold, validateProbability, releaseReservation, CONFIG } from './blog-study.js';

test('budget counts concurrent reservations and rejects unknown values', () => {
  assert.doesNotThrow(() => budgetCheck(1, 2, 3));
  assert.throws(() => budgetCheck(8, 1, 2));
  assert.throws(() => budgetCheck(NaN, 0, 0));
});
test('floating point reservation release cannot become negative', () => {
  let n = .1 + .2; n = releaseReservation(n,.1); n = releaseReservation(n,.2);
  assert.ok(n >= 0); assert.equal(releaseReservation(.3-.1,.2),0);
  assert.doesNotThrow(() => budgetCheck(.002, n, .01));
});
test('threshold is learned on calibration and defers all if none meet rule', () => {
  assert.equal(chooseThreshold(Array.from({length: 200}, () => ({correct: false, score: .99}))).threshold, null);
  const rows = [...Array.from({length: 100}, () => ({correct: true, score: .9})), ...Array.from({length: 100}, () => ({correct: false, score: .2}))];
  const t = chooseThreshold(rows);
  assert.equal(t.accepted,100); assert.equal(t.errors,0); assert.equal(t.threshold,.25);
});
test('probabilities reject invalid scores rather than coercing them', () => {
  assert.equal(validateProbability(0),0); assert.equal(validateProbability(1),1);
  for (const value of [null, undefined, '0.9', -1, 1.1, NaN]) assert.throws(() => validateProbability(value));
});
test('four fast systems are fixed; no Sol, Flex or batch', () => {
  assert.equal(CONFIG.length,4);
  assert.ok(CONFIG.some(m => m.model === 'google/gemini-3.8-flash'));
  assert.ok(CONFIG.every(m => !/sol|flex|batch/i.test(m.model+' '+m.tag)));
});
test('frozen splits have 77-intent coverage, unique independent IDs, and timing repeats only', async () => {
  const s=JSON.parse(await readFile(new URL('./blog-study/splits.json',import.meta.url),'utf8'));
  assert.deepEqual(Object.fromEntries(Object.entries(s).map(([k,v]) => [k,(v as unknown[]).length])),{development:50,calibration:200,test:500,repeat:50});
  const all = [...s.development,...s.calibration,...s.test] as {id:string;text:string;expected:string}[];
  assert.equal(new Set(all.map(r=>r.id)).size,750);
  assert.equal(new Set(all.map(r=>r.text.toLowerCase().replace(/\s+/g,' ').trim())).size,750);
  assert.equal(new Set(s.test.map((r:{expected:string})=>r.expected)).size,77);
  assert.ok(s.repeat.every((r:{id:string})=>s.test.some((t:{id:string})=>r.id===t.id)));
});
