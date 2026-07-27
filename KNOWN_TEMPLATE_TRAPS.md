# Known template traps: moved

This registry outgrew a single file and now lives in its own repository,
where anyone can add entries:

**<https://github.com/Blackwellboy/model-serving-minefield>**

This stub stays here so existing links keep resolving. Every entry that
lived in this file is there, restructured symptom-first, one file per trap,
with the same evidence and attributions:

| Old entry | New location |
|---|---|
| #1 The reasoning field has two names | [traps/01-reasoning-field-two-names.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/01-reasoning-field-two-names.md) |
| #2 Orphaned `</think>` leaking into content | [traps/02-orphaned-think-close-tag.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/02-orphaned-think-close-tag.md) |
| #3 `enable_thinking` default drifts between revisions | [traps/03-enable-thinking-default-drift.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/03-enable-thinking-default-drift.md) |
| #4 Prior-turn reasoning stripped from history | [traps/04-history-reasoning-stripping.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/04-history-reasoning-stripping.md) |
| #5 A scoring detail silently flips a verdict | [traps/05-scorer-normalization-verdict-flip.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/05-scorer-normalization-verdict-flip.md) |
| #6 Identity-sentence eviction | [traps/06-identity-sentence-eviction.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/06-identity-sentence-eviction.md) |
| #7 `reasoning_effort` accepted and silently ignored | [traps/07-reasoning-effort-silently-ignored.md](https://github.com/Blackwellboy/model-serving-minefield/blob/main/traps/07-reasoning-effort-silently-ignored.md) |

The build-scoping rule that lived in this file's preamble (thinking policy
differs by build, not just revision; state build AND revision next to every
number) is now rule 2 of the registry's
[methodology preamble](https://github.com/Blackwellboy/model-serving-minefield#methodology-preamble).

The registry also ships the template forensics preflight
([checks/preflight_template.py](https://github.com/Blackwellboy/model-serving-minefield/blob/main/checks/preflight_template.py))
that catches the trap-04 class before a lane is certified.

If a serving path burned you and the number survived review, add it there:
[report a trap](https://github.com/Blackwellboy/model-serving-minefield/issues/new?template=report-a-trap.yml).
