# Live News Shock Archive

Purpose: prospectively archive structured news-shock observations for the ETF rotation strategy.

Storage policy:
- Keep structured daily audit records in normal Git as JSONL/CSV so they remain diffable, searchable, and easy to consume in research scripts.
- Do not store full copyrighted news article bodies. Store source metadata, URLs, timestamps, short factual summaries, and extracted market-impact fields.
- Use Git LFS only for genuinely large binary evidence when needed (for example screenshots or exported market snapshots). Most daily records should not require LFS.

Suggested path:
- data/live-news/YYYY-MM.jsonl

Recommended fields per record:
- audit_date
- symbol
- asset_name
- role: incumbent | target | candidate
- signal_date
- execution_date
- etf_open_gap_pct
- etf_close_return_pct
- underlying_name
- underlying_overnight_return_pct
- underlying_intraday_return_pct
- event_category: macro | supply_demand | policy | geopolitical | industry | company | none
- event_time_local
- known_before_open: true | false | unknown
- source_name
- source_url
- source_published_at
- factual_summary
- shock_direction: positive | negative | mixed | none
- shock_severity: 0-3
- existing_gap_filter_triggered
- suspected_filter_miss
- suspected_false_alarm
- hypothesis_tag
- notes

Research discipline:
1. Archive what was knowable at the time; do not rewrite old records using later information.
2. News is an observation layer, not a discretionary override of the frozen live strategy.
3. Parameter changes require later OOS aggregation and explicit validation.
4. Preserve negative examples and false alarms, not only successful warnings.
