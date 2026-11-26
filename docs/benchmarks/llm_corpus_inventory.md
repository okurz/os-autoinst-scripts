# Corpus inventory: how many tickets hide behind the LLM-commented jobs? (poo#210528)

Measured 2026-11-26, read-only, before any label audit work
(`tasks/022_poo210528_verdict_label_reaudit.md`, Task 1.1). It answers one question: does the o3
corpus carry enough distinct tickets to replace the 50-row / 7-ticket verdict dataset with a
ticket-diverse one.

## Method

```sh
scripts/benchmarking/fetch_eval_dataset.py --inventory --limit 5000 \
  --groups $(curl -s https://openqa.opensuse.org/api/v1/job_groups | jq -r '.[].id' | tr '\n' ' ') \
  --since 2026-05-26 --until 2026-11-26
```

`tests/list_ajax` answers `comment=LLM` for finished jobs only, takes no date filter and no page/offset
(the route uses `complex_query` with a fixed `t_finished DESC` order), and is capped server-side at
`misc_limits.all_tests_max_finished_jobs` = 5000 rows per request. A global query therefore covers only
about one month (2026-11-01 .. 2026-11-26), so the corpus was assembled from one query per job group:
112 groups from `/api/v1/job_groups`, deduplicated by job id, then filtered client-side on `finished`.
The windows are inclusive and the query is read-only; `--inventory` writes no dataset.

## Result

| Month | LLM-commented jobs |
|---|---|
| 2026-05 (from the 26th) | 891 |
| 2026-06 | 4128 |
| 2026-07 | 4576 |
| 2026-08 | 7089 |
| 2026-09 | 6370 |
| 2026-10 | 7887 |
| 2026-11 (to the 26th) | 4937 |
| **Total** | **35878** |

**616 jobs (1.7%) carry a human bug reference**, the other 35262 have none and cannot serve as ground
truth. Those 616 rows reference **195 distinct tickets**, by tracker: `poo` 118, `boo` 48, `gh` 19,
`bsc` 8, plus two non-ticket labels (`kde#502830`, `bootloader_uefi#1`).

| Reference | Rows | Reference | Rows |
|---|---|---|---|
| `poo#206028` | 40 | `boo#1289464` (v1 dataset, 21 rows) | 21 |
| `poo#201381` | 33 | `poo#198215` | 18 |
| `poo#194576` | 29 | `bsc#1290026` | 17 |
| `poo#198767` | 27 | `poo#179278` | 15 |
| `poo#209382` (v1 dataset, 13 rows) | 27 | `boo#1230849` | 15 |

96 of the 195 references carry at least two rows, 32 carry five or more. Capping every ticket at five
rows — the plan's Task 1.4 rule — leaves **430 scorable rows over 195 tickets**, against 50 rows over 7
tickets today.

## Coverage caveat

Four groups exceed the 5000-row cap, so their history inside the window is clipped and the counts above
are a lower bound for them:

| Group | Rows fetched | Oldest in-window job | Window months lost |
|---|---|---|---|
| 1 | 5000 | 2026-06-05 | 2026-05-26 .. 06-04 |
| 3 | 5000 | 2026-06-18 | 2026-05-26 .. 06-17 |
| 38 | 5000 | 2026-08-19 | 2026-05-26 .. 08-18 |
| 132 | 5000 | 2026-07-18 | 2026-05-26 .. 07-17 |

The other 108 groups reach back to 2026-05-26 or beyond within the window. Closing the gap would need a
date-filtered or paginated listing, which `tests/list_ajax` does not offer; a `job_setting` split
(`BUILD`, `FLAVOR`) per group is the only lever the endpoint leaves, and it is not needed here: the
truncation can only *understate* the ticket count, which is what the decision below depends on.

## Consequence for the label re-audit

H3 is confirmed, with margin: the corpus yields 195 distinct tickets, not the 40 the plan targeted and
far above the falsifier's floor of 25. At the plan's power table, ~195 independent decisions resolve a
difference of roughly 11 points at 80% power (alpha 0.05), so the 12-point Inkling gap is at the edge of
what the extended corpus can measure; the cluster bootstrap decides whether it separates.

Two inputs to the next tasks:

- **Ticket identity is not the same as a `boo`/`poo` prefix.** `gh#…` references (19 tickets) need the
  tracker mapping the audit already used (`gh#os-autoinst/os-autoinst-distri-opensuse` → test code,
  other `gh#` → product), and the two label-shaped references must be dropped from scoring.
- **`--max-per-ticket 5` is the binding rule for the dataset**, not the job count: the corpus offers 430
  rows at that cap, so the v2 dataset is limited by the audit effort per ticket, not by supply.
