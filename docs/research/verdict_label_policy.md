# Verdict label policy

How a benchmark row's ground truth is decided (`tasks/022_poo210528_verdict_label_reaudit.md`,
Task 1.2). The existing dataset derives every label from the tracker a bug reference happens to live in
(`boo`/`bsc` → `product`, `poo` → `test`), which survives neither a WONTFIX closure nor two tickets that
describe one symptom in opposite trackers. This policy replaces the tracker mapping with a rule that is
written before the audit, applied to the ticket's content and state, and reproducible by a second reader
(H4).

## Classes

The three classes are the tool's own verdict values, quoted from the question it must answer
(`openqa-llm-investigate`, `VERDICT_QUESTION`):

| Tool answer | Policy class | The tool's definition |
|---|---|---|
| `Product bug` | `product` | "the software under test is wrong, e.g. a kernel panic or segfault" |
| `Test issue` | `test` | "test code, needle or test data is wrong" |
| `Infrastructure problem` | `infra` | "only if the analysis shows an error of the worker, its network or an external server, not of the tested system itself" |

`unclear` is a fourth, unscored outcome: the ticket does not decide the class, so no model can be right
or wrong on that row. A class the policy cannot defend is recorded as `unclear` with its reason rather
than guessed, because a guessed label is exactly what this audit exists to remove.

The tracker a reference lives in is a **prior, not a label**: `boo`/`bsc` references usually describe
product defects and `poo` tickets usually describe test-suite work, but the class follows from what the
ticket says and what state it is in.

## Decision rules

Applied in order to the ticket's summary, description and first comments, then to its state. The first
rule that matches decides.

1. **`infra`** when the ticket names only a worker, network or external-service fault (dead worker, DNS
   or mirror outage, an external API returning errors) and nothing in the product under test.
2. **`test`** when the ticket names a defect in test code, needles or test data — a wrong test module
   path, a broken needle, a schedule or YAML error, a test-side assertion or branching bug.
3. **`test`** when the ticket describes a product behaviour change that the test suite must absorb: the
   product now behaves as designed and the test's expectation is stale. This is the decisive rule for the
   `esc` case below, where a GNOME menu change makes `boot_to_desktop` press a key that no longer works.
4. **`product`** when the ticket names a defect in the software under test — a boot, installer, package,
   filesystem or SELinux defect the test reproduces — and its state does not contradict the conclusion.
5. **`product`** when the state records a product conclusion without naming the component in the visible
   content: `RESOLVED/FIXED` on a ticket whose symptom is a product failure.
6. **`unclear`** otherwise: closed `INVALID`/`WONTFIX` without a product conclusion (the ticket was
   discarded, not resolved), no content beyond the summary, a reference that is not a ticket at all
   (`kde#…`, `bootloader_uefi#…`), or a contradiction per the section below.

Rule 3 is the one the tracker mapping gets backwards: a product change that the test must follow is a
`test` issue for this benchmark, because the fix belongs in the test suite, and the model is asked what
caused *this job's* failure, not whether the product change was intended.

**The `esc` case, decided explicitly.** `boo#1289464` ("[QE] openQA test fails in boot_to_desktop —
'esc' key does not exit menu anymore", GNOME change since snapshot 20261101, still IN_PROGRESS) and
`poo#209751` (the same symptom, "the test needs to press it differently") describe one phenomenon in two
trackers. Rules 3 and the contradiction rule disagree with `boo#1289464`'s own label, so the policy
declares the rows `unclear` until a human rules on the pair: the audit records both scorings (with the
21 rows as `test`, and without them) and never presents one as the measurement.

A row with several references takes the class of the reference that names the cause of *this* failure; if
two references on the same row disagree, the row is `unclear`.

## Confidence

Each label carries one of three confidence levels:

| Level | Meaning |
|---|---|
| `certain` | The ticket content names the failing component or code path and the state is consistent with the class (e.g. a line-move in `bootloader_setup.pm`, a `match_has_tag` branching bug, an in-progress product defect with a named package). |
| `plausible` | The content supports the class but does not name the concrete failing path, or the state neither confirms nor contradicts it (`RESOLVED/FIXED` without a visible fix note, a summary-only match). |
| `unclear` | Rule 6: not scored. |

Scored rows are `certain` and `plausible`. The class balance and the all-`product` ceiling of the dataset
are computed on the scored rows only; the `plausible` rows are reported separately so the reader can see
how much of the result rests on the weaker half.

## Contradictions

When two tickets describe the same symptom in opposite classes, the policy does not break the tie:

- both tickets' rows are `unclear` from the moment the pair is identified until a human rules;
- the pair, its two references and the date it was recorded go into the dataset documentation;
- every reported accuracy states which of the two scorings it uses, or is given twice.

A human ruling — recorded here with its evidence, approver and date — resolves the pair: the rows then
take the ruled class with confidence `certain`, and the ruling is cited with the row. Absent such a
ruling the rows stay unscored, so the audit cannot silently convert a disagreement into a label.

### Ruling: the `esc` pair (okurz, 2026-11-26)

`boo#1289464` is `product` and `poo#209751` is `test`. The pair is not a contradiction once the product
defect and its test-side workaround are told apart:

- `boo#1289464` tracks a real product defect found by openQA: GNOME stopped letting `esc` exit the
  overview menu after snapshot 20261101, reported upstream as
  <https://gitlab.gnome.org/GNOME/mutter/-/work_items/5200> and fixed in
  <https://src.opensuse.org/GNOME/mutter/pulls/21>, with the package updates
  <https://build.opensuse.org/request/show/1397154> and its follow-up.
- `poo#209751` is the test adaptation: the test has to press the key differently (PR 27264), a workaround
  that keeps the suite green while the product fix lands.

The failing job therefore showed a product issue; the test change is the workaround, not the cause. Both
sets of rows are scored — `boo#1289464` as `product`, `poo#209751` as `test` — and the dataset records the
ruling instead of forcing them `unclear`.
