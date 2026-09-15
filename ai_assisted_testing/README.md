# AI-assisted testing

Two scripts, matching the two halves of "AI can assist in test case
generation and data verification":

## `generate_test_cases.py` — test case generation
Documents and reproduces the actual process used to expand
`tests/api/test_invoices_api.py`'s hand-written boundary cases:

1. The existing cases were shown to Claude with a prompt asking for
   additional edge cases a human might not think of unassisted.
2. Every suggestion was manually reviewed — see `ai_generated_test_cases.json`,
   where each case has a `review_note`. Some were accepted, some marked
   `"ambiguous"` because the AI could describe a plausible edge case but not
   reliably predict Xero's real validation behaviour for it.
3. Ambiguous cases are wired into `tests/api/test_ai_generated_cases.py` as
   explicit `pytest.skip()`s with the reason shown — so running the suite
   surfaces "these N cases still need a real check against Xero" instead of
   the uncertainty getting lost in a JSON file.

Run `python generate_test_cases.py` (with your own `ANTHROPIC_API_KEY` set)
to reproduce the generation step and see fresh suggestions.

## `verify_data_with_ai.py` — data verification
A second-pass, advisory anomaly check for data that has already passed
deterministic quality rules (completeness, uniqueness, validity). It looks
for softer issues — near-duplicate contact names, mismatched
description/account-code pairs, likely duplicate entries — the kind of
thing a human reviewer might catch by eye but a rigid rule wouldn't.

This is explicitly **advisory, not a gate**: deterministic checks (dbt
tests / Great Expectations in the data pipeline) remain the pass/fail
authority. AI output here is a second opinion for a human to look at, not
an automated approval or rejection.

Run `python verify_data_with_ai.py` (with your own `ANTHROPIC_API_KEY` set)
against the included sample records — one pair is a deliberate near-duplicate
(`Alice Smith` / `Alice Smyth`, same amount and description) to check the
model actually catches it rather than rubber-stamping the batch.

## Why this is structured this way
The honest claim here isn't "AI wrote my tests" — it's "AI widened the net
of candidate cases and flagged some second-pass anomalies, and I applied
the same judgement a tester always has to apply to decide what's real,
what's redundant, and what needs more information before it's trustworthy."
That review step, made visible rather than hidden, is the actual skill.
