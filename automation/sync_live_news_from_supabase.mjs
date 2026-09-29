const SUPABASE_URL = 'https://gsyziuzezmmnvgdoazkg.supabase.co';
const SUPABASE_KEY = 'sb_publishable_8jFjtjpds8Bn6dwV5bPSOg_DMX8NfcZ';

const r = await fetch(
  `${SUPABASE_URL}/rest/v1/live_news_audits?select=audit_date,payload&order=audit_date.asc`,
  { headers: { apikey: SUPABASE_KEY } }
);
if (!r.ok) throw new Error(`Supabase fetch failed: ${r.status} ${await r.text()}`);
const rows = await r.json();
const groups = new Map();
for (const row of rows) {
  if (!row?.audit_date || !row?.payload) continue;
  const month = row.audit_date.slice(0, 7);
  if (!groups.has(month)) groups.set(month, []);
  groups.get(month).push(row.payload);
}
const fs = await import('node:fs/promises');
await fs.mkdir('data/live-news', { recursive: true });
for (const [month, payloads] of groups) {
  const text = payloads.map(x => JSON.stringify(x)).join('\n') + '\n';
  await fs.writeFile(`data/live-news/${month}.jsonl`, text, 'utf8');
  console.log(`synced ${month}: ${payloads.length} rows`);
}
