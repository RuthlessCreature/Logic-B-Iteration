# Agent / Goal work contract
Focus on **capital-based replay** (CNY 10000, 2020-01-01..2026-06-30) before model polishing.
Do not reactivate H01/H02 legacy workflows. Old assets are under legacy/2026-10-15-pre-reset/.
Next: 1) validate new pure-Python accounting smoke, 2) build Xuangubao/BaoStock ingest with caching and date coverage, 3) full-window replay and year-by-year equity ledger, 4) LLM candidate proposals plus chronological validation, 5) human FOLLOW/NO_FOLLOW report.
No automatic real orders, force push, main edits, or protected 2026-07-01..09-28 market data.
If data absent, report the exact missing days, not invented net values. Keep all code and reports reproducible.
