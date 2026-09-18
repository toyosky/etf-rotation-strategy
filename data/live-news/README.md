# Live News Shock Archive

Purpose: prospectively archive text-based news-shock observations for the ETF rotation strategy.

Storage policy:
- Store text only. Do not archive screenshots, images, PDFs, HTML snapshots, or other binary evidence.
- Keep structured daily audit records in normal Git as JSONL so they remain diffable, searchable, and easy to consume in research scripts.
- Preserve source metadata, URL, publication time, a short source excerpt when useful, factual extraction, and the model's analysis.
- Do not copy full copyrighted news articles. Retain only the minimum excerpt needed to preserve the contemporaneous evidence, plus an independent factual summary and analysis.
- Git LFS is not required for this archive unless the policy changes later.

Path:
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
- source_title
- source_excerpt
- factual_summary
- analysis
- shock_direction: positive | negative | mixed | none
- shock_severity: 0-3
- existing_gap_filter_triggered
- suspected_filter_miss
- suspected_false_alarm
- hypothesis_tag
- notes

Research discipline:
1. Archive only what was knowable at the time; do not rewrite old records using later information.
2. Separate source text, factual extraction, and analysis so later review can distinguish evidence from interpretation.
3. News is an observation layer, not a discretionary override of the frozen live strategy.
4. Parameter changes require later OOS aggregation and explicit validation.
5. Preserve negative examples and false alarms, not only successful warnings.
