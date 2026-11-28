# Benchmark Report: Inkling-2-Mini (UD-Q4_K_M, Mainline_Support layout) on AMD EPYC 7773X

- **Date**: 2026-11-22
- **Candidate**: `unsloth/Inkling-2-Mini-GGUF`, file `Mainline_Support/Inkling-2-Mini-UD-Q4_K_M.gguf_file` renamed to `.gguf` (16,610,544,608 bytes = 15.47 GiB)
- **Architecture**: `inkling2_loop`, 24 physical blocks, loop `start=6 end=18 count=3` → 48 layer applications per token; 128 experts, 8 used, 2304 embedding, native ctx 1048576
- **Test Host**: w26 — AMD EPYC 7773X (128 threads), 512 GiB, AVX2; production container on 8080 co-tenant
- **Harness**: `ghcr.io/ggml-org/llama.cpp:server-b12627` (build 12627, commit `225a5345b`), isolated port 8082
- **Dossier**: `docs/research/inkling2_mini.md` (facts, H1-H6, adopt and kill criteria)
- **Quality replay**: os-autoinst-scripts-benchmarking `docs/benchmarks/inkling2_mini_verdict.md` (full-50, two runs, same-build control)

## Deployment configuration

Pre-pull and rename as user `llama`, outside the 300 s health window of the deploy script (15.47 GiB,
63 s):

```sh
mkdir -p /opt/llm/models/inkling
curl -sL -o /opt/llm/models/inkling/Inkling-2-Mini-UD-Q4_K_M.gguf \
  https://huggingface.co/unsloth/Inkling-2-Mini-GGUF/resolve/main/Mainline_Support/Inkling-2-Mini-UD-Q4_K_M.gguf_file
```

Deploy with the production flag set, the local path and the card's sampling:

```sh
./scripts/benchmarking/deploy_candidate.sh start --worker w26 \
  --image ghcr.io/ggml-org/llama.cpp:server-b12627 \
  --model-path /root/.cache/huggingface/inkling/Inkling-2-Mini-UD-Q4_K_M.gguf \
  --server-args "--jinja --top-p 1.0 --top-k 0 --min-p 0.0" "" 8082 64 65536
```

The script appends the extra flags after its hardcoded `--top-p 0.95 --top-k 64`, so the server warns
`DEPRECATED: argument '--top-p' specified multiple times` and `--top-k` likewise and keeps the last
value: `/props` reports `top_p 1.0, top_k 0, min_p 0.0`. Health window: the container reached
`/health` in 8 s. The 32-thread configuration is the same command with `32`.

`llama-server --version` from the pinned image reports `build 12627, commit 225a5345b`. Against a clone
of master at `8a97fa98a`, `git merge-base --is-ancestor` confirms both merge commits are in that build:
#32694 `29b52d398` (28 commits earlier) and #32704 `690b87d88` (17 commits earlier). `server-b12602` is
the published tag with #32694 and 9 commits behind #32704, so it is not usable for the
`Mainline_Support` layout.

## Load result

Loader lines (verbosity 3, 64 threads):

```
load_model: loading model '/root/.cache/huggingface/inkling/Inkling-2-Mini-UD-Q4_K_M.gguf'
load: special_eos_id is not in special_eog_ids - the tokenizer config may be incorrect
init: llama threadpool init, n_threads = 64
load_model: initializing, n_slots = 4, n_ctx_slot = 65536, kv_unified = 'true'
init: chat template supports preserving reasoning, it is enabled by default
model loaded
```

`n_layer`, `arch` and the expanded slot count are not printed at verbosity 3, so the layout is taken from
the GGUF header: `general.architecture = inkling2_loop`, `general.name = Inkling-2-Mini`,
`inkling2_loop.block_count = 24`, `loop.start = 6`, `loop.end = 18`, `loop.count = 3`,
`loop.gate_rank = 64`, `expert_count = 128`, `expert_used_count = 8`, `context_length = 1048576`,
`embedding_length = 2304`. 24 + (3 − 1) × (18 − 6) = **48 layer applications per token**, the plan's
loop arithmetic. `/v1/models` reports the model name as the file path; `/props` carries the sampling
values above.

The template loaded with jinja (`--jinja` was passed, and the reasoning-preservation warning is the
served template's own), and the EOS warning above is the tokenizer's, not a layout failure. No tensor,
arch or loader error occurred.

## Perplexity

The published `server` image ships `/app/llama-server` only; `llama-perplexity` is available in
`ghcr.io/ggml-org/llama.cpp:full-b12627`. No committed 1M-character sample exists in the harness, so
the sample is the 79,469 characters of this repository's own `docs/**/*.md`, fed as natural prose:

| Model | File | Sample | PPL |
|---|---|---|---|
| **Inkling-2-Mini** | `Mainline_Support` `UD-Q4_K_M` | 79,469 chars of repo prose, 5 chunks at `n_ctx` 8192, 64 threads | **3.45 ± 0.07** |
| gemma-4-26B-A4B-it (control, known-good) | `UD-Q4_K_M` | same file | 113.5 ± 6.1 |

The card's reference band is 7.65 for `Q8_K_XL` on its own corpus and ≈ 130 for the root layout on a
mainline build. Inkling's 3.45 is inside the sane region and a factor of 38 below the gibberish
region, so the layout trap did not fire. PPL is corpus-relative: the incumbent on the same file measures
113.5, which is why the comparison is qualitative and not a band.

Two probes that do not carry weight are recorded so they are not re-run: a deterministic 256-token
completion on a 60-token prompt produced coherent analysis text (self-likelihood 1.06, a greedy
repetition artifact — the incumbent measures 1.06 on the same prompt while producing token soup), and
`llama-perplexity` on 100,211 characters of the harness's own repeated log line measured 1.0057, which
is the repetitiveness of the synthetic sample, not the model.

The root-layout file was not downloaded, so the dossier's second falsifier (root layout measuring sane on
mainline) stays unmeasured. The layout is pinned by the header, the PPL above, and 100% verdict parse
rate in the quality replay.

## Throughput

Cold probes (prefix cache disabled), 64 threads, `--ctx-size 65536`, one container restart per
configuration:

| Model | Quant | Weights | Prompt tokens | Cold wall (s) | Prefill (s) | Prefill tok/s | Decode tok/s | Threads |
|---|---|---|---|---|---|---|---|---|
| **Inkling-2-Mini** | `UD-Q4_K_M` | 15.47 GiB | 1711 | 28.62 | 25.9 | 65.99 | 12.29 | 64 |
| **Inkling-2-Mini** | `UD-Q4_K_M` | 15.47 GiB | 8391 | 108.75 | 105.2 | 79.73 | 8.87 | 64 |
| **Inkling-2-Mini** | `UD-Q4_K_M` | 15.47 GiB | 14244 | 208.47 | 202.3 | 70.40 | 5.06 | 64 |
| Inkling-2-Mini | `UD-Q4_K_M` | 15.47 GiB | 8391 | 214.00 | 210.4 | 39.87 | 9.19 | 32 |
| gemma-4-26B-A4B-it (control) | `UD-Q4_K_M` | 15.8 GiB | 8643 | 44.76 | 43.2 | **200.15** | **21.71** | 64 |

The control row was measured on the same day, host and pinned build at the same prompt size, and it
corrects an earlier reading of this report: comparing Inkling's 79.73 tok/s against the matrix's
recorded 68 tok/s cache-miss figure for the incumbent (build 8740) suggested prefill parity, but gemma
prefills at **200.15 tok/s** on `b12627` with a comparable prompt. Both legs are therefore a loss:
prefill 2.5x, decode 2.4x, wall time 2.4x (44.76 s against 108.75 s for ~8.4k prompt tokens). The
recorded 68 tok/s row is not comparable — different build, prompt and cache state — and the same-day
probe is the number to quote.

Decode decays faster than prefill: 12.3 tok/s at 1.7k, 8.9 at 8.4k, 5.1 at 14.2k tokens. Halving the
threads from 64 to 32 halves prefill (79.7 → 39.9 tok/s) and leaves decode flat (8.87 → 9.19 tok/s): the
loop cost is bandwidth-bound, not parallelism-bound, so thread scaling buys nothing for the decode leg
that an investigation spends most of its time in.

H1 (decode below 23 tok/s) is confirmed, and the 48-slot model is slower than the incumbent's 3.8 B
active MoE on both legs at every prompt size measured.

## Reasoning effort

The same 8.1k prompt (8406 prompt tokens) through `params_proxy.py` at four levels; the template maps
`none 0.0, minimal 0.1, low 0.2, medium 0.7, high 0.9, xhigh/max 0.99` and defaults to 0.9 when the
request carries none:

| Level (effort) | Completion tokens | Wall (s) | Proxy `wall_sec` |
|---|---|---|---|
| `none` (0.0) | 828 | 315.35 | 315.19 |
| `minimal` (0.1) | 453 | 224.79 | 224.64 |
| `medium` (0.7) | 695 | 331.97 | 331.82 |
| `high` (0.9, template default) | 1098 | 339.57 | 339.41 |

Output tokens grow 2.43× from 0.1 to 0.9 (453 → 1098), so H3's growth clause holds. 0.9 is not
monotone against 0.0: `none` produced 828 tokens, more than `minimal`, so the mapping is not a linear
token budget. The 4096-token-per-turn ceiling in the kill criteria is not reached at any level.

The full-50 replay uses `minimal` (0.1), the level with the lowest completion tokens and wall time and
zero jobs at the budget. It is not the deployed shape: `openqa-llm-investigate` sends no
`reasoning_effort`, so the model runs at its 0.9 default. The replay therefore measures the candidate at
the most favourable effort, and the 0.9 column is the deployed cost.

## Timeout budget

Criterion "13.8k-token prefill ≤ 400 s at 64 threads": measured 202.3 s prefill at 14,244 tokens, so it
holds. The 600 s gateway budget: 0 of 50 jobs reached it in both full runs (max 469.2 s), and the
sweep's 0.9 level at 8.1k takes 339.6 s for one turn, which projects to ≈ 500-1000 s for the tool's
three turns at the default effort — the effort sweep is the axis that decides whether the deployed shape
fits, and at 0.9 it is at the edge of the budget. p90 per job at the selected effort is 324.7 s (run 1)
and 145.3 s (run 2), above the plan's 300 s kill threshold in run 1.

## Host state during the runs

w26 load average (1/5/15 min): 3.04/14.71/8.58 before the probes, 2.11 at the control deploy,
0.02/3.76/26.05 after the control run. `/opt` free: 402 GiB before the pull, 386 GiB after. The
production container on 8080 stayed up and healthy throughout; the benchmark container
`llama-bench-8082` is the only unit that was started and stopped.

## Effort replay (2026-11-23)

The effort axis was re-measured after the report above, because a reasoning model scored only at its
lowest effort is not scored at its capability. Full 50-job replay at `medium` (0.7), same container,
same flags, same tool revision, quiet host:

| Arm | Accuracy | `Test` P / R | Median | p90 | Max | 600 s |
|---|---|---|---|---|---|---|
| effort 0.1, run 1 | 48.0% (24/50) | 21.4% / 16.7% | 190.9 s | 324.7 s | 469.2 s | 0 |
| effort 0.1, run 2 | 50.0% (25/50) | 29.4% / 27.8% | 82.6 s | 145.3 s | 233.1 s | 0 |
| **effort 0.7** | **48.0% (24/50)** | 26.7% / 22.2% | 230.0 s | 388.0 s | 476.2 s | 0 |
| gemma control | 62.0% (31/50) | 0.0% / 0.0% | 192.9 s | 326.1 s | 481.3 s | 0 |

Accuracy is flat across the two effort levels (24/50 both times, 43 of 50 verdicts identical to run 2),
so the 12-14 point gap to the control is capability, not a reasoning budget that a higher effort would
have unlocked. Effort 0.7 also produces one `Infrastructure problem` answer, a class the dataset never
labels. Marked-commit jobs answered `Test issue`: 2/6 at 0.1 run 1, 4/6 at 0.1 run 2, 3/6 at 0.7, 0/6
for the control — that axis moves with sampling, not with effort.

## Drafter (DSpark)

Task 4.1 measured the model's own speculative drafter, `dspark-Inkling-2-Mini-Q8_0.gguf` (402,278,560
bytes, arch `dflash`, 3 blocks, `vocab_size` 201024 / `vocab_size_unpadded` 200058) against the
`Mainline_Support` Q4_K_M file on `server-b12627`:

```sh
./scripts/benchmarking/deploy_candidate.sh start --worker w26 --image ghcr.io/ggml-org/llama.cpp:server-b12627 \
  --model-path /root/.cache/huggingface/inkling/Inkling-2-Mini-UD-Q4_K_M.gguf \
  --draft /root/.cache/huggingface/inkling/dspark-Inkling-2-Mini-Q8_0.gguf \
  --spec-type draft-dspark --spec-draft-n-max 3 --server-args "--jinja" "" 8084 64 65536
```

### DSpark throughput

**Not measurable: the loader rejects the published drafter.** With `--spec-type draft-dspark` and again
with `draft-dflash`, the server exits during load:

```
common_speculative_init_result: loading draft model '.../dspark-Inkling-2-Mini-Q8_0.gguf'
llama_model_load: error loading model: check_tensor_dims: tensor 'markov_w1.weight' has wrong shape;
  expected 256, 200058, got 256, 201024, 1, 1
srv load_model: failed to load draft model
```

Both files declare `vocab_size` 201024 and `vocab_size_unpadded` 200058, so the `inkling2_loop` base asks
for the unpadded width while the `dflash` drafter stores the padded one: an upstream mismatch in
`b12627`, not a flag error. No decode gain can be measured until upstream accepts the pair.

### Accept rate

Not measured, because the draft model never loads. The container log carries no acceptance counter
(`n_drafted`, `n_accept`) for the same reason.

### Output equality

Not measured. `compare_spec_outputs.py` needs both endpoints, and the drafted one never became healthy,
so greedy equality with the draftless server is unverified either way.

## Quant escalation

Task 4.2 measured `Mainline_Support` `UD-Q4_K_XL` (16.42 GiB, 17,629,760,736 bytes) on the same build and
flags. Q8_K_XL was not downloaded: the plan allows it only if Q4_K_XL shows a gain, and it showed none.

### Quant escalation throughput

| Quant | Weights | Prompt tokens | Prefill tok/s | Decode tok/s | Cold wall |
|---|---|---|---|---|---|
| `UD-Q4_K_M` (primary) | 15.47 GiB | 8391 | 81.65 | 8.83 | 106.44 s |
| `UD-Q4_K_XL` | 16.42 GiB | 8391 | 81.73 | 8.76 | 106.37 s |

The two runs of Q4_K_XL bracket a first probe of 52.49 tok/s prefill and 4.10 tok/s decode taken while
the host load average was 103 from the co-tenant production container; the pair above was measured back
to back, so the 6% larger file costs nothing measurable in throughput.

## Full-50 replay

| Arm | Accuracy | `Test` P / R | Median | p90 | Max | 600 s | Agreement with Q4_K_M run 2 |
|---|---|---|---|---|---|---|---|
| `UD-Q4_K_XL`, effort 0.1 | **48.0% (24/50)** | 28.6% / 27.8% | 155 s | 259 s | 354 s | 0 | 46/50 |

The extra bits buy no accuracy: identical 24/50, `Test` precision 28.6% against the 50% bar, one
`Infrastructure problem` answer the dataset never labels, and 46 of 50 verdicts shared with the Q4_K_M
run. Quantisation is not the cause of the 12-14 point gap to the control.

## Matched-configuration arms (2026-11-24)

The candidate's arms differed from the control in sampling, reasoning preservation and effort, so three
further full-50 arms removed those differences one at a time (details and the control row in
os-autoinst-scripts `inkling2_mini_verdict.md`):

| Arm | Accuracy | `Product` | `Test` P | Median | p90 | Max |
|---|---|---|---|---|---|---|
| card sampling, effort 0.1 | 25/50 (50%) | 20/32 | 29% | 83 s | 145 s | 233 s |
| production sampling, effort 0.1 | 23/50 (46%) | 18/32 | 26% | 169 s | 272 s | 487 s |
| production sampling, `--no-reasoning-preserve`, `--reasoning-budget 1024`, effort 0.1 | 24/50 (48%) | 20/32 | 27% | 148 s | 225 s | 415 s |
| production sampling, `--no-reasoning-preserve`, effort 0.9 | 25/50 (50%) | 21/32 | 29% | 307 s | 531 s | 960 s |

`--no-reasoning-preserve` is worth keeping in any future Inkling measurement: it cuts p90 by 47 s with no
accuracy change. Effort 0.9 is not deployable: p90 531 s and two jobs lost to the runner's 900 s job
timeout, with no accuracy gain over 0.1. On the 38 jobs whose label is readable from the job's own logs the
candidate reaches 22-24 against the control's 31, so sampling, prompt handling, effort and the unreachable
test labels together explain none of the gap.

## Ticket-level label audit (2026-11-26)

Every label in the 50-job dataset comes from `comment_data.bugs` of the investigated job, mapped by
tracker: Bugzilla reference → `product`, progress reference → `test`. The 50 rows carry **7 distinct
tickets**, so each model is scored on about seven decisions rather than fifty:

| Ticket | Rows | Label | State | Content |
|---|---|---|---|---|
| `boo#1289464` | **21** | product | IN_PROGRESS | "[QE] openQA test fails in boot_to_desktop — 'esc' key does not exit menu anymore", a GNOME change from snapshot 20261101 |
| `poo#209382` | 13 | test | In Progress | line-move hack in `bootloader_setup.pm` corrupts the grub config |
| `boo#1246013` | 5 | product | IN_PROGRESS | MicroOS `setup-fips` with BLS leaves setup incomplete |
| `poo#209802` | 4 | test | New | `match_has_tag` branching bug |
| `boo#1289038` | 3 | product | RESOLVED/**WONTFIX** | AutoYaST clone failure, closed for missing logs |
| `boo#1288617` | 3 | product | RESOLVED/**FIXED** | SELinux denials |
| `poo#209751` | 1 | test | In Progress | the **same 'esc' symptom**, "the test needs to press it differently" |

`boo#1289464` and `poo#209751` label one phenomenon in opposite classes because they live in different
trackers, and `boo#1289038` is a WONTFIX. The earlier dataset audit examined only the 18 `test` labels;
the product side was inherited unverified.

Re-scored on the 26 rows whose ticket content clearly supports the label: Inkling 13/26 (50%) against the
gemma control 8/26 (31%), paired 5 to 0 for Inkling (McNemar p = 0.06). On the tracker labels it is the
other way round (25/50 against 31/50). The comparison turns on one labelling decision covering 42% of the
dataset, so the rejection in `## Verdict` below holds only for the tracker labels and no adoption or
rejection is defensible until the labels are re-audited on a larger, ticket-diverse sample
(`tasks/022_poo210528_verdict_label_reaudit.md`). The throughput, layout and drafter findings are
independent of the labels and stand.

## Verdict

The deciding measurement is the full-50 replay against the control on the same pinned build
(os-autoinst-scripts-benchmarking `docs/benchmarks/inkling2_mini_verdict.md`): Inkling **48.0% (24/50)**
and **50.0% (25/50)** in two runs, against gemma-4-26B-A4B-it's **62.0% (31/50)** on `server-b12627`,
with `Test` precision 21-29% under the 50% bar and run-to-run agreement 86% under the 90% bar.

**Do not adopt** — and the later units closed the remaining escapes: the drafter does not load at all, the
larger quant is identical in accuracy (24/50) and throughput, and the production shape costs one job in 16,
so neither engine tuning nor the deployment penalty explains the gap.

**Do not adopt.** Criteria 3, 4, 6 and 7 pass (median 190.9 and 82.6 s ≤ the control's 192.9 s, p90
324.7/145.3 s ≤ 600 s, zero jobs at the 600 s budget, 202.3 s prefill at 14.2k tokens ≤ 400 s, pinned
upstream image, accuracy under the 74.0% ceiling); criteria 1, 2 and 5 fail. The conditional units were measured anyway on 2026-11-23 at okurz's request
(`## Approvals`), and each came back negative: the DSpark drafter is rejected by the loader, `Q4_K_XL`
scores the same 48.0% with no throughput change, and the production shape costs 1 of 16 jobs. The tool
flag `--llm-reasoning-effort` was written and tested in a separate worktree, defaulting to unset.

The one axis Inkling moves is real and worth naming: `Test` recall leaves zero, and 4 of the 6 jobs whose
prompt carries a marked test commit get the correct class at effort 0.1, where the incumbent gets 0 of 6.
That is prompt-evidence behaviour, reproducible with any model that uses the commit the prompt already
contains, so it is an argument for the tool change plan 006 named, not for a model swap. 12 of 18
`test` labels stay unreachable for every model.

Production consequence: the w26/w27 quadlet stays exactly as it is. Gate 1 in the plan remains unmet, the
floating `server` tag and the `--top-p 0.95 --top-k 64` sampling stay in place, and the card's sampling
flags are applied to no container. The harness additions (`--model-path`, `--server-args`,
`params_proxy.py`) stay in the repos and are the measurement path for the next candidate.
