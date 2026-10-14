Logic-B H02 Local Codex handoff package

1) Read HANDOFF_H02.md first.
2) Paste CODEX_START_PROMPT.txt as first instruction in local Codex.
3) patches/h02_hardening_v2_20261014.patch is P0; patches/h02_portfolio_price_guard_20261014.patch is P1.
4) Don't copy files from this package directly over the repository. Review then git apply --check before applying.
5) The code must remain on research/behavioral-edge-20261013; do not modify main or access protected holdout.
