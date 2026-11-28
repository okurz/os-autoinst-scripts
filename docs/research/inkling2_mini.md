# Candidate dossier: Inkling-2-Mini (poo#210528)

Research date: 2026-11-22. Candidate for the `openqa-llm-investigate` backend on `openqaworker26`/`27`,
evaluated against `gemma-4-26B-A4B-it:UD-Q4_K_M` (62.0% (31/50), 202 s median / 356 s p90 per
investigation, 0% `Test` recall), the post-plan-006 reference recorded in os-autoinst-scripts
`docs/benchmarks/gemma4_verdict_regression.md`. This file records facts and pre-registered criteria; the
measurements and the verdict live in `docs/benchmarks/inkling2_mini.md` (this repository) and
`docs/benchmarks/inkling2_mini_verdict.md` (benchmarking repository).

## TL;DR

`unsloth/Inkling-2-Mini-GGUF` (base `thinkingmachines/Inkling-2-Mini`) is the first candidate since plan
003 that runs on upstream `llama.cpp`, the first looped model (24 physical layers, 48 layer applications
per token, 3.4 B active weights, 5.4 B effective active) and the first with a reasoning-effort knob the
served template turns on by default (0.9). The three measurement axes the harness lacks today are the
layout of the GGUF, `--jinja`, and the effort level; this dossier records the harness work they force.

## Facts

Verified 2026-11-22 against the HF card, the `llama.cpp` master log and source, and a read-only probe of
w26 and the w26 quadlet.

### Model, quants and loop arithmetic

| Fact | Value |
|---|---|
| Base model | `thinkingmachines/Inkling-2-Mini`, Apache-2.0, released 2026-11-20, 26.2 B total / 3.4 B active, MoE routing 8 of 128 experts, hybrid local/global attention, 1M ctx, natively multimodal |
| Loop arithmetic | 24-layer decoder, middle 12 layers run 3x: `n_layer_all = n_phys + (passes - 1) * (core_end - core_start)` = 24 + 2×12 = **48 layer applications per token**, so 5.4 B effective active weights per token |
| GGUF repo | 10 UD quants: IQ1_S 7.23 GiB, IQ1_M 7.47, IQ2_XXS 7.90, Q2_K_XL 8.51, IQ3_XXS 10.86, Q3_K_XL 12.70, IQ4_XS 14.65, **Q4_K_M 15.47 GiB (primary)**, Q4_K_XL 16.42, Q8_K_XL 21.30 |
| Card KLD | Q4_K_M 0.0108 / 97.9% same top token; Q3_K_XL 0.0174 / 96.3% |
| Drafter | `dspark-Inkling-2-Mini-Q8_0.gguf` 0.37 GiB (repo root), arch `dflash`, `--spec-type draft-dspark`, `--spec-draft-n-max` clamped to 7 (trained block 8); README states greedy equality with a draftless server is not guaranteed |
| Card limits | "sometimes became stuck in long reasoning loops … recommend setting limits on output tokens"; "support for looped models in local runtimes is new, and speed varies by runtime and hardware"; LongBench v2 66.9%, MRCR 8-needle 256-512K 46.4% |

### Two layouts, and the rename step

| Fact | Value |
|---|---|
| Root files | Unsloth's looped layout, arch `inkling2`; need Unsloth's own build |
| Mainline files | `Mainline_Support/*.gguf_file`, arch `inkling2_loop`; **must be renamed to `.gguf` after download** |
| Card warning | mainline on the root layout gives gibberish: PPL ~130 vs 7.65 on `Q8_K_XL` |

The rename is part of the pre-pull, not of the container: as user `llama`, download
`Mainline_Support/Inkling-2-Mini-UD-Q4_K_M.gguf_file` (15.47 GiB, outside the 300 s health window) into
the cache volume `/opt/llm/models`, rename it to `Inkling-2-Mini-UD-Q4_K_M.gguf`, and start the container
pointed at the container-side path `/root/.cache/huggingface/inkling/Inkling-2-Mini-UD-Q4_K_M.gguf`.
Perplexity on the renamed file gates every later measurement: a value near 130 means the wrong layout and
voids every number after it.

### Upstream support, image pins and the ancestry check

| Fact | Value |
|---|---|
| Master support | `inkling2`/`inkling2_loop` in `src/llama-arch.cpp`, models `src/models/inkling2.cpp` and `inkling2-loop.cpp` (the loop core expansion above) |
| PR #32694 | "Inkling 2 Mini", merged 2026-11-20T22:01Z |
| PR #32704 | "inkling2_loop re-share the loop slots after the scale pass", merged 2026-11-21T11:10Z |
| Published server tags | `server-b12464` (2026-11-17, no inkling), `server-b12602` (2026-11-21T09:13Z, has #32694, **9 commits behind #32704**), **`server-b12627`** (2026-11-22T06:01Z, includes both merges); the floating `server` tag resolves to `b12627` today, master is `8a97fa98` (2026-11-22T06:28Z) |

The criterion is commit ancestry, not the date: the pinned image must contain both merge commits. Read the
commit the image is built from out of the server binary and test both merges against it (the container run
is one-shot, read-only, and needs confirmation like every host action):

```sh
hash="$(podman run --rm ghcr.io/ggml-org/llama.cpp:server-b12627 --version | grep -oE '\(\w{8}\)' | tr -d '()')"
git -C llama.cpp merge-base --is-ancestor "$(git -C llama.cpp log --grep 'Inkling 2 Mini' --merges -1 --format=%H)" "$hash" && echo "#32694 in"
git -C llama.cpp merge-base --is-ancestor "$(git -C llama.cpp log --grep 're-share the loop slots' --merges -1 --format=%H)" "$hash" && echo "#32704 in"
```

`server-b12627` passes both; `server-b12602` passes the first and fails the second. The loader lines
(`arch`, `n_layer`, the expanded slot count) and `/v1/models` are recorded per run, so a layout or
build mismatch is visible in the report, not inferred from the version string.

### Chat template, `--jinja`, and the reasoning-effort knob

| Fact | Value |
|---|---|
| Template | jinja-only: macros, `namespace`, `raise_exception`, `{% generation %}`; EOS `<|content_model_end_sampling|>` |
| `llama.cpp` default | master reads `use_jinja = false` (`common/arg.cpp:1381`) and older builds follow it, so **`--jinja` is mandatory** there; `server-b12627` reports `--jinja ... (default: enabled)`, so the flag is harmless but no longer required on that build |
| Effort mapping | template maps none 0.0, minimal 0.1, low 0.2, medium 0.7, high 0.9, xhigh/max 0.99, and **defaults to 0.9** when the request carries no effort |
| Forwarding | the server passes the request's `reasoning_effort` into the chat-template kwargs (`tools/server/server-common.cpp:1641`) |
| Tool request | `openqa-llm-investigate` sends `model`, `messages` and `temperature` only, `TEMPERATURE = 0.3` — no `reasoning_effort`, no `num_ctx` |
| Sampling | card recommends temp 1.0, top-p 1.0, top-k off, min-p 0; the deployed server defaults (top-p 0.95, top-k 64, min_p 0.05) apply to the tool's requests because the tool sends only temperature |

The pinned build also exposes `--reasoning-effort` as a server flag, `--reasoning-budget N` (a hard cap
on thinking tokens, aimed at the card's reasoning-loop warning) and `--no-reasoning-preserve` (the load
warning says preserving the trace may use more tokens), so a fixed level or a budget costs no proxy.

The effort axis is measurable without touching the tool: `openqa-llm-investigate` changes are out of scope
by plan 006, so effort, `top_p`/`top_k`/`min_p` and `num_ctx` are injected by the benchmarking proxy
(Task 2.1) and the replay points at the proxy. Changing the tool's request is the conditional Task 4.3 and
is gated.

### Harness today, host, and the production shape

| Fact | Value |
|---|---|
| `deploy_candidate.sh` | has `--worker`, `--image`, `--draft`, `--spec-type`, `--spec-draft-n-max`; hardcodes `--temp 1.0 --top-p 0.95 --top-k 64`; **no `--jinja`, no local model path**, so a renamed `Mainline_Support` file cannot be deployed |
| Needed additions | `--model-path <path>` (emits `-m <path>`, no `-hf`, model positional becomes optional) and `--server-args "<flags>"` (appended verbatim after the existing flags), byte-identical command line when both are absent, resolved target echoed |
| Host | w26 (EPYC 7773X, 128 threads, 512 GiB), load 0.12 and 402 GiB free on `/opt` at 2026-11-22; benchmark port 8082, production 8080 |
| Production quadlet (read 2026-11-22) | floating `ghcr.io/ggml-org/llama.cpp:server`, `-hf unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M --threads 64 --ctx-size 65536 --cache-ram 65536 -ctk q8_0 -ctv q8_0 -fa on --no-mmproj --temp 1.0 --top-p 0.95 --top-k 64` |
| Gateway | `proxy_read_timeout 600s`, 4 server slots, prompt 1 truncated at 4096 tokens |
| Reference numbers | incumbent 62.0% (31/50), `Test` recall 0%, 202 s median / 356 s p90 (build 8740, tool `22575395`); as deployed through `o3-llm`, 19 product / 1 test of 20 stratified jobs, 268 s median / 652.9 s p90; ceilings 64.0% constant-`Product` and 74.0% prompt-side evidence |

## Hypotheses

H1 (compute). 48 layer applications cost more per token than the incumbent's MoE, so prefill lands below
68 tok/s and decode below 23 tok/s at 8.1k context. Falsified by a `bench_throughput.py` probe at 8.1k
that reaches >= 23 tok/s decode with the Mainline_Support file.

H2 (layout trap). The root-layout GGUF on a mainline build produces gibberish; the `inkling2_loop` file
does not. Falsified if a perplexity probe on the Mainline_Support file exceeds ~12, or if the root file
measures sane PPL on `b12627`.

H3 (effort). The template's default effort 0.9 dominates latency: output tokens per turn grow by more than
2x compared with effort 0.1 on the same prompt, and the verdict changes with effort. Falsified if the
effort sweep shows a flat output-token count and identical verdicts across 0.1/0.7/0.9.

H4 (quality). The looped model's extra depth moves accuracy above the incumbent and gets `Test issue`
recall off zero. Falsified if the full-50 replay lands within 3 points of the incumbent control measured
on the same build.

H5 (ceiling). Accuracy cannot pass 74.0% because the tool never fetches the evidence 12 of 18 `test`
labels need. Falsified by accuracy > 74.0% with correct `Test` verdicts on jobs whose prompt 1 carries no
marked test commit.

H6 (stability). The looped server degrades cache slots under long traffic (the Ornith `erased invalidated
context checkpoint` trap), so verdicts and latency drift with run order. Falsified if two full runs of one
configuration agree on >= 90% of verdicts and the control run reproduces the control.

## Measurement matrix

| Axis | Values | Purpose |
|---|---|---|
| Layout | root `inkling2` vs `Mainline_Support/inkling2_loop` | the gibberish trap decides everything after it |
| Image | pinned `server-b12627`; incumbent control on the same build | isolates model from build drift |
| Quant | Q4_K_M primary; Q4_K_XL/Q8_K_XL only on a near-miss | KLD says Q4_K_M ~ Q4_K_XL |
| Threads | 64 (production parity), 32 (loop scaling) | 48 layer applications may scale differently |
| Prompt size | ~1.6k, ~8.1k, ~13.8k tokens | 13.8k prefill is the 600 s proxy risk |
| Effort | 0.1, 0.7, 0.9 (default) via the proxy | output-token inflation, latency, verdict stability |
| Sampling | top-p 1.0 / top-k 0 / min-p 0 vs the server defaults 0.95/64/0.05 | the card's recommendation vs the deployed quadlet |
| Quality set | all 50 jobs, two runs, plus the incumbent control on the same build | comparable with 62.0% |
| Production shape | 4 slots, `num_ctx` 4096, stratified 20 jobs | the deployment penalty the gateway applies |
| Drafter | `draft-dspark` at n-max 3, greedy equality check | latency from the looped model's own drafter |
| Vision | not measured (`--no-mmproj`) | text-only investigation workload |

Every endpoint run uses `bench_throughput.py` for timings and
`run_investigate_eval.py --llm-timeout 600 --retries 1 --dry` for accuracy, on isolated port 8082, with the
replay executed on the o3 host because SSH port forwards stall long requests.

## Decision criteria

Adopt `Inkling-2-Mini` over the incumbent only if all seven hold:

1. full-50 accuracy >= 68.0% (6 points over the same-build control),
2. `Test issue` recall >= 25% with precision >= 50% — the incumbent is at 0% and this is the axis the
   production reviews are judged on,
3. median per investigation <= the same-build control's median, p90 <= 600 s, and zero jobs reaching the
   600 s gateway budget,
4. 13.8k-token prefill <= 400 s at 64 threads,
5. two full runs agree on >= 90% of verdicts,
6. it runs on a pinned upstream image with committed flags — no fork, no source build to maintain,
7. accuracy <= 74.0%, or the excess is explained by evidence the prompt now carries; above the prompt-side
   ceiling the labels must be re-checked before the number is believed.

A tie is not a win: the incumbent stays if Inkling only reaches the constant-`Product` ceiling.

## Kill criteria

Stop the evaluation and report instead of tuning if any of these fire:

- `server-b12627` rejects the `inkling2_loop` GGUF (arch/tensor/loader error), or the jinja template is
  rejected at startup;
- perplexity on the Mainline_Support file exceeds ~12, or the root file measures sane on mainline — the
  layout trap is real and every later number is void;
- 13.8k-token prefill exceeds 400 s, p90 per job exceeds 300 s, or any job hits the 600 s budget;
- effort 0.9 output exceeds 4096 tokens per turn (the card's reasoning-loop warning), so latency is
  unbounded at the deployed effort;
- accuracy within 3 points of the same-build control, or a degenerate single-class answer pattern;
- verdicts stop parsing (`**LLM Investigation summary:**` header missing) — that is the tool's chat-template
  handling, record the evidence and stop; this plan does not patch the tool.

## Production consequence

Adopting Inkling moves the w26/w27 quadlet image off the floating `server` tag to a pinned build at or
above `server-b12627`, replaces the model with the renamed `Mainline_Support` Q4_K_M file, adds `--jinja`,
and changes the sampling flags to `--top-p 1.0 --top-k 0 --min-p 0.0`. Those flags currently serve the
incumbent too, so the change is plan 002 Task 3.1, needs okurz's approval and a production window; the
gate recorded 2026-11-22 is **unmet** (the quadlet shows the floating tag, `UD-Q4_K_M`, `--top-p 0.95
--top-k 64`, no `--jinja`). Rejecting Inkling keeps the quadlet unchanged.
