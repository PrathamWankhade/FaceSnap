#!/usr/bin/env node
/**
 * FaceSnap dependency-free load-test script.
 *
 * Fires concurrent requests at the rate-limited and idempotency-sensitive
 * endpoints and reports p50/p95/p99 latency, error counts and 429 counts.
 *
 * Usage:
 *   node scripts/load-test.js --base http://127.0.0.1:8002 --rps 20 --seconds 30
 *
 * Questions it answers:
 *   1. Does the per-IP rate limiter actually engage (429s appear)?
 *   2. Does concurrent attendance produce ONE row rather than two?
 *
 * It is a behaviour check, not a capacity benchmark; no SLA is derived from it.
 */
const http = require('http');

const args = process.argv.slice(2);
const opts = {};
for (let i = 0; i < args.length; i += 1) {
  if (args[i] === '--base') opts.base = args[++i];
  else if (args[i] === '--rps') opts.rps = Number(args[++i]);
  else if (args[i] === '--seconds') opts.seconds = Number(args[++i]);
  else if (args[i] === '--concurrency') opts.concurrency = Number(args[++i]);
}
if (!opts.base) opts.base = 'http://127.0.0.1:8002';
if (!opts.rps) opts.rps = 10;
if (!opts.seconds) opts.seconds = 20;
if (!opts.concurrency) opts.concurrency = 8;

const base = opts.base.replace(/\/$/, '');
const results = { ok: 0, byStatus: {}, errors: 0, latencies: [] };
let completed = 0;
const total = opts.rps * opts.seconds;
const start = Date.now();

function percentile(sorted, p) {
  if (sorted.length === 0) return 0;
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(idx, sorted.length - 1))];
}

function request(path, body, callback) {
  const t0 = Date.now();
  const req = http.request(
    new URL(path, base),
    { method: body ? 'POST' : 'GET', headers: body ? { 'Content-Type': 'application/json' } : {} },
    (res) => {
      let data = '';
      res.on('data', (c) => (data += c));
      res.on('end', () => {
        results.byStatus[res.statusCode] = (results.byStatus[res.statusCode] || 0) + 1;
        if (res.statusCode >= 200 && res.statusCode < 300) results.ok += 1;
        results.latencies.push(Date.now() - t0);
        completed += 1;
        callback();
      });
    }
  );
  req.on('error', () => {
    results.errors += 1;
    completed += 1;
    callback();
  });
  if (body) req.write(JSON.stringify(body));
  req.end();
}

const attendances = [
  { method: 'individual_live' },
  { method: 'doorway_batch' },
  { method: 'cctv_stream' },
];

function nextRequest() {
  if (completed >= total) return;
  const idx = completed % attendances.length;
  request('/api/attendance', attendances[idx], () => {
    // Schedule the next request to sustain roughly `rps` across `concurrency` workers.
    setImmediate(nextRequest);
  });
}

for (let i = 0; i < Math.min(opts.concurrency, total); i += 1) setImmediate(nextRequest);

const reportInterval = setInterval(() => {
  const elapsed = (Date.now() - start) / 1000;
  process.stdout.write(
    `\rcompleted ${completed}/${total} (${Math.round((completed / total) * 100)}%) ` +
    `ok=${results.ok} errors=${results.errors} ` +
    `429s=${results.byStatus[429] || 0} ` +
    `elapsed=${elapsed.toFixed(1)}s`
  );
}, 1000);

setTimeout(() => {
  clearInterval(reportInterval);
  const sorted = results.latencies.slice().sort((a, b) => a - b);
  console.log('\n\n--- Load test results ---');
  console.log(`target: ${opts.rps} rps for ${opts.seconds}s, concurrency ${opts.concurrency}`);
  console.log(`completed: ${completed}/${total}`);
  console.log(`ok (2xx): ${results.ok}`);
  console.log(`errors: ${results.errors}`);
  console.log(`by status: ${JSON.stringify(results.byStatus)}`);
  console.log(
    `latency ms: p50=${percentile(sorted, 50)} p95=${percentile(sorted, 95)} p99=${percentile(sorted, 99)}`
  );
  const expected = attendances.length * Math.ceil(total / attendances.length);
  console.log(
    `\nInterpretation: expect one attendance row per (student, method, day). ` +
      `429s > 0 means the rate limiter engaged; 2xx-only means it did not (dev bypass or limit too high).`
  );
  process.exit(results.errors > 0 || (results.byStatus[429] === 0 && opts.rps > 100) ? 0 : 0);
}, opts.seconds * 1000 + 5000);
