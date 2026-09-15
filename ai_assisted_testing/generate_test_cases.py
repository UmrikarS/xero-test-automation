"""
AI-assisted test case generation.

This documents the actual process used to produce
ai_generated_test_cases.json, so it can be re-run or extended rather than
being a one-off, unverifiable claim.

Process (honest account, not automated end-to-end):
1. The hand-written boundary cases already in tests/api/test_invoices_api.py
   were shown to Claude along with the prompt below.
2. Claude suggested additional edge cases a human reviewer might not think
   of unassisted (very large numbers, whitespace-only strings, type
   coercion, Unicode, length boundaries).
3. EVERY suggestion was manually reviewed before being added to
   ai_generated_test_cases.json -- see each case's "review_note" field.
   Several were marked "ambiguous" rather than accepted outright, because
   the AI could describe a plausible edge case but could not reliably
   predict Xero's actual validation behaviour for it. Those need a real
   run against the Demo Company to resolve before becoming hard pytest
   assertions -- they are documented as open questions, not silently
   guessed at.

Why this matters for a QA role: the value of AI here isn't "generate tests
and trust them blindly" -- it's "generate a wider net of candidate cases,
then apply the same judgement a human tester would to decide which are
real, which are redundant, and which need more information before they can
be automated." That review step is the actual skill being demonstrated.

This script re-issues the same prompt via the Anthropic API so the process
is reproducible, rather than just describing it after the fact. It requires
your own ANTHROPIC_API_KEY (see https://console.anthropic.com) -- this
project does not ship with one.
"""
import json
import os
from pathlib import Path

import requests

PROMPT = """\
Here are the boundary-value test cases already covering invoice UnitAmount
and Contact Name validation in a Xero API test suite:

- UnitAmount: 100.00 (valid-typical), 0.01 (valid-boundary-low),
  0.00 (invalid-boundary), -50.00 (invalid-negative)
- Contact Name: a normal name (valid), an empty string "" (invalid)

Suggest additional edge cases for these two fields that a human tester
might not think of unassisted. For each case, state:
1. What it tests and why it's a meaningful edge case (not just a random
   variation)
2. The specific input value
3. Whether you can confidently predict pass/fail, or whether it's genuinely
   ambiguous without checking the real system's documented behaviour

Do not guess at Xero-specific validation rules you aren't certain about --
say "ambiguous, needs verification" rather than inventing a confident
answer.
"""


def generate_candidate_cases():
    """
    Calls the Anthropic API with the prompt above and returns the raw
    response text. This is the reproducible half of the process --
    the review/curation step (see ai_generated_test_cases.json) still
    has to be done by a human afterwards.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set ANTHROPIC_API_KEY to reproduce this generation step. "
            "The already-reviewed output of a prior run is checked in at "
            "ai_generated_test_cases.json."
        )

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": PROMPT}],
        },
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def load_reviewed_cases():
    """Loads the already-curated cases for use in tests -- this is what
    tests/api/test_ai_generated_cases.py actually imports at test time."""
    path = Path(__file__).parent / "ai_generated_test_cases.json"
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    print("Regenerating candidate cases via the Anthropic API...\n")
    candidates = generate_candidate_cases()
    print(candidates)
    print(
        "\n--- These are raw AI suggestions. Review each one manually and "
        "update ai_generated_test_cases.json accordingly -- do not wire "
        "unreviewed suggestions directly into the pytest suite. ---"
    )
