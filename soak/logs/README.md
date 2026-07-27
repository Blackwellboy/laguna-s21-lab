# `turns.jsonl` withdrawn, 2026-07-28

The raw per-turn log of the 12h soak used to live here. It was withdrawn on
2026-07-28 because a whole-tree re-scan of the published tip found internal
identifiers in its model-generated response previews that this repository had
documented as already replaced: a node codename, fleet topology, and
control-plane vocabulary quoted from the soak's private ingest corpus.

It was withdrawn rather than patched. The previews are model-generated, so a
future batch could leak in a shape no substitution table anticipates, and the
soak's value is its aggregate result rather than 2,900 raw previews.

The log is retained privately. Everything needed to check the published
numbers stays here: `sessions.jsonl`, `incidents.jsonl`,
`integrity_probes.jsonl`, `service_samples.jsonl`, the soak report in
`../LAGUNA_SOAK_12H_20260725_RESULTS.md`, and the driver and scoring scripts.

Full correction: `../../REDACTIONS.md`.
