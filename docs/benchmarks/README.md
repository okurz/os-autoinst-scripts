# Benchmark records

- [gemma4_verdict_regression.md](gemma4_verdict_regression.md) and [llm_verdict_dataset_audit.md](llm_verdict_dataset_audit.md): the verdict quality of `openqa-llm-investigate` on the 50-job dataset, and why its verdicts collapse to one class.
- [gemma4_mtp_qat.md](gemma4_mtp_qat.md) and [gemma4_speculative_qat.md](gemma4_speculative_qat.md): the llama.cpp MTP draft-head and QAT-weight evaluation for the same model, with its dossier.
- [gemma_26b_a4b.md](gemma_26b_a4b.md), [model_variations_benchmark.md](model_variations_benchmark.md), [ornith_9b_gsq_rco.md](ornith_9b_gsq_rco.md) and [swift_qwen38_27b.md](swift_qwen38_27b.md): the candidate record — the incumbent's baseline, the quantisation and context-size variations, and the two candidates that were measured and rejected.
- [inkling2_mini.md](inkling2_mini.md) and [inkling2_mini_verdict.md](inkling2_mini_verdict.md): the looped-`inkling2_loop` candidate — throughput, deployment and effort handling, and its quality replay against a same-build control.

## Verdict reference caveat

Every verdict percentage in the records below is measured on `tests/data/eval_dataset.json`, whose 50 rows
come from 7 tickets, one of them covering 21 rows. A ticket-content audit replaced those labels:
`tests/data/eval_dataset_v2.json` holds 204 scored rows over 84 tickets under the written policy in
`docs/research/verdict_label_policy.md`, and [verdict_dataset_v2.md](verdict_dataset_v2.md) records that
the policy reproduces on 16 of 20 rows against an independent reading. Read the numbers below as the
record of what was measured on that sample, not as a model ranking; the ticket-diverse comparison lives
in that file.

The benchmark harness is in `scripts/benchmarking/`: `deploy_candidate.sh` starts and stops an isolated candidate container on an openQA worker, `fetch_eval_dataset.py` builds the dataset from the API, and `bench_throughput.py`, `run_investigate_eval.py`, `compare_spec_outputs.py` and `score_verdicts.py` measure it.

The design and the decision it serves are in [../spec/SPEC-cpu-llm-benchmarking.md](../spec/SPEC-cpu-llm-benchmarking.md) and [../intent/cpu-only-llm-models-o3.md](../intent/cpu-only-llm-models-o3.md); the background reads
in [../research/cpu-only-llm-inference.md](../research/cpu-only-llm-inference.md) and [../research/ornith_1_5_9b_gsq_rco.md](../research/ornith_1_5_9b_gsq_rco.md).

## Tool revisions

The verdict-quality records name tool revisions by what they changed rather than by commit hash,
because those changes were evaluated before they were upstream:

| Name used in the records | What it changes |
|---|---|
| pre-normalisation revision | reads the verdict without normalising it first |
| normalisation revision | normalises the verdict before reading it |
| base revision | the normalisation revision plus formatting only; the classification path is identical to the current revision |
| current revision | spells the verdict lines out and moves the classification into the summary header |
| rule-based fix | adds a rule that names the cause explicitly; measured and reverted |
| revert | drops the rule-based fix |
