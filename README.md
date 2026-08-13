# Lumin Fund Research Dashboard

A single-file dashboard (`lumin-portfolios.html`) showing the Lumin model
portfolios (full rebalance history), fund research pages, manager-note links
and a team calendar. Model data is extracted from the Model Portfolio Analysis
workbook and spliced into the HTML as a seeded data block.

## Which surface is canonical

| Thing | Canonical location |
|---|---|
| Workbook (source of truth for model data) | `Copy of Model Portfolio Analysis - V4.3.11.xlsx` in the **LWM Investment Team - Portfolio Analysis Excel** SharePoint library. Confirmed 13 Aug 2026 as the location the team uses going forward. Read locally via its OneDrive-synced copy under `~\Lumin Wealth Management\`. |
| Dashboard code + data pipeline | **This repo.** `lumin-portfolios.html` here is THE file; edit it directly, never a copy. |
| Published dashboard | The claude.ai artifact is a published copy, refreshed from the repo file. Under Dagster automation (planned) a SharePoint-hosted copy becomes the primary surface instead. |

## Refreshing the data

```
python scripts/refresh_dashboard.py        # or double-click refresh-dashboard.bat
```

The script auto-locates the synced workbook, extracts every model, and
rewrites the seed block in the repo HTML plus any synced SharePoint copy of
the dashboard it finds. Provenance (workbook save time, refresh time, latest
rebalance) lands in `SEED_META` and shows in the dashboard's freshness banner.
Each run's stats append to `data/run_log.json`.

Safety gates - the script refuses to run/publish if:

- any `Model Weights` sheet name has no parseable date (rename it or add to
  `DATE_OVERRIDE`);
- the extract shrank vs the previous run (models, snapshots or funds fell) -
  usually a renamed sheet or broken column. Re-run with `--allow-shrink` only
  if the shrink is intentional.

Soft warnings (off-100% totals, unmatched columns, dropped placeholder
columns) print at the end of the run; review them, they do not block.

Other scripts:

- `scripts/extract_funds.py` - regenerates `data/funds.json` (fund register).
  Derives the newest `Model Weights` sheet and the workbook path at runtime.
- `scripts/build_notes_map.py` - regenerates `data/notes_map.json` with
  SharePoint web URLs for manager meeting notes.

## Data contract for the workbook

The workbook is hand-edited; the pipeline can only defend against what it can
detect. These rules are the integrity system:

1. **One workbook.** No `- Copy` variants, ever. The canonical file lives in
   the library above and nowhere else.
2. **Rebalance sheets** are always named `Model Weights - From DD.MM.YYYY`,
   year included. Anything else either fails the refresh (no date) or needs a
   manual `DATE_OVERRIDE` entry.
3. **Weights are decimal fractions** (0.045 = 4.5%). Model columns are named
   `L<risk>_<platform>` (or recognised variants); non-model columns are
   ignored by pattern.
4. **Master Holdings List** maps UNID/ISIN to fund name, share class and
   asset class (Cash / Equities / Fixed Interest / Diversifiers). Every held
   fund should have a row; misses fall back to the raw sheet name.
5. **Fund note folders** on SharePoint are named exactly as the fund appears
   in the Master Holdings List.

## Reconciliation

First live-workbook refresh (13 Aug 2026) is evidenced in
[docs/reconciliation-2026-08-13.md](docs/reconciliation-2026-08-13.md):
v2-to-v3 diff explained, 61 warnings reviewed, 4 models spot-checked against
raw workbook cells, all matched.
