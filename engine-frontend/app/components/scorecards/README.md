# Scorecards components

`routes/scorecards.tsx` shows one person's scorecard at a time (PRD K1 to K4) at `/scorecards?person=<id>`. The status rule lives in `lib/scorecard.ts`.

| File | Notes |
| --- | --- |
| `met-adder.tsx` | Tag a person on a metric: calendar suggestions, then search. Also used by the Home scorecard |
| `edit-scorecard-drawer.tsx` | Add, rename or remove a person's metrics: count (tags) or yes or no, with a weekly target |
| `metric-status-chip.tsx` | On track, At risk, Behind |

Demo data lives in `demo/scorecards-data.ts`.
