import { neon } from '@neondatabase/serverless';
import { readFile } from 'node:fs/promises';

if (!process.env.RATE_LIMIT_TEST_DATABASE_URL) throw new Error('Set RATE_LIMIT_TEST_DATABASE_URL to an isolated branch');
const sql = neon(process.env.RATE_LIMIT_TEST_DATABASE_URL);
if (process.argv.includes('--inspect')) {
  const rows = await sql`select pg_get_functiondef(p.oid) as definition from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname = 'take_token'`;
  console.log(rows.map(row => row.definition).join('\n'));
  process.exit(0);
}
const migration = await readFile(new URL('../migrations/001_rate_buckets.sql', import.meta.url), 'utf8');
const functionOffset = migration.indexOf('CREATE OR REPLACE FUNCTION');
if (functionOffset < 0) throw new Error('Missing migration function');
for (const statement of migration.slice(0, functionOffset).split(';').map(s => s.trim()).filter(Boolean)) {
  await sql.query(statement);
}
await sql.query(migration.slice(functionOffset));
if (process.argv.includes('--apply')) {
  console.log('Migration applied.');
  process.exit(0);
}
const key = `migration-check-${crypto.randomUUID()}`;
const results = await Promise.all(Array.from({ length: 12 }, () =>
  sql`select allowed from public.take_token(${key}, ${10}, ${0.0001})`));
const allowed = results.filter(rows => rows[0].allowed).length;
await sql`delete from public.rate_buckets where key = ${key}`;
if (allowed !== 10) throw new Error(`Expected 10 allowed requests, got ${allowed}`);
console.log('Migration and concurrent token consumption verified on isolated branch.');
