# Reconciliation evidence - v2 to v3 seed refresh, 13 August 2026

This records the first refresh of the dashboard against the live SharePoint
workbook, per the reconciliation plan (Phase 1, step 5). It is the evidence
that the dashboard now equals the workbook.

## Source

- Workbook: `Copy of Model Portfolio Analysis - V4.3.11.xlsx` in the
  LWM Investment Team SharePoint library, read via the OneDrive-synced copy at
  `~\Lumin Wealth Management\LWM Investment Team - Portfolio Analysis Excel\`.
  Hugh confirmed (13 Aug 2026) this library is the canonical location the team
  will use for Model Portfolio Analysis going forward.
- Sync completed 09:20; first refresh 11:54; verification re-run ~12:30 against
  the workbook as saved at 12:00 (the file is actively edited and the sync is
  live).

## What changed, v2 seed (git HEAD) vs v3 seed (refreshed)

| Stat | v2 (2026-05-01 seed) | v3 (refreshed) | Why |
|---|---|---|---|
| Latest rebalance | 2026-05-01 | 2026-08-03 | New rebalance sheet `Model Weights - From 03.08.26` added to the workbook after the v2 seed was cut. |
| Rebalance dates | 40 | 41 | Same. |
| Models | 17 | 75 | v2 seeded Core from ARC only plus 12 current-only WZ models (the 2026-08-11 decision). That was reversed on 2026-08-12: every platform's full Core history is now seeded so the dashboard can filter by provider (`CANONICAL_CORE_PLATFORM = None`). |
| Snapshots | 212 | 1,358 | Follows from seeding all platforms' histories. |
| Platforms | 16 | 17 | FidSL (Fidelity SL SIPP) appears in the 06.08.2025 sheet. Its columns are 0.5% cash-only placeholders, so its 5 snapshots were dropped as empty; only the platform label is new. |
| Funds | 170 | 170 | Unchanged. |

## Warnings review (61 total, none blocking)

- 5 warnings: FidSL L10-L90 @ 2025-08-06 total 0.50% each. Placeholder
  columns (cash line only). Correctly dropped from the seed as empty
  snapshots; the UI never sees them.
- 56 warnings: snapshots totalling 84.5% to 103.5%, all in historical sheets
  dated 2017-05-02 to 2023-07-27 (concentrated in 2017-2018 Asc/ARC/SL/AXA
  columns). This is genuine workbook content from before current practice;
  the extractor keeps these rows as-is and the dashboard flags off-100%
  snapshots in the UI. Every sheet from 2025 onward totals clean, including
  the new 03.08.26 sheet.

## Spot checks (raw workbook cells vs the spliced SEED block)

Method: an independent script read the weight columns straight off the sheets
with openpyxl (no shared extraction logic) and compared fund-by-fund against
the seed by ISIN and weight.

| Model | Result |
|---|---|
| Core ARC L50 @ 2026-08-03 (`L50_ARC` on `Model Weights - From 03.08.26`) | 19 rows, 100.00% both sides; 18 ISIN-exact matches plus the Cash line (no ISIN) matched by name. MATCH. |
| Passive WZ L50 (`Passive Allocations`) | 18 rows, 100.00% both sides, all exact. MATCH. |
| ESG WZ L50 (`ESG Allocations`, `L50 ESG`) | 18 rows, 100.00% both sides, all exact. MATCH. |
| Income WZ L50 (`L50 Income`) | 19 rows, 100.00% both sides, all exact. MATCH. |

## Run stats (also in `data/run_log.json`)

170 funds | 41 dates | 17 platforms | 75 models | 1,358 snapshots |
33 manager-notes links | 5 dropped empty snapshots | latest rebalance 2026-08-03.

## Conclusion

The v3 seed faithfully reproduces the live workbook. The v2-to-v3 deltas are
fully explained by (a) the new 03.08.26 rebalance and (b) the deliberate
all-platforms seeding decision of 2026-08-12. No unexplained data movement.
