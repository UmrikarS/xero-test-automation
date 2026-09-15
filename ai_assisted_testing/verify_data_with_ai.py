"""
AI-assisted data verification.

Complements generate_test_cases.py: that script uses AI to help find test
CASES; this one uses AI to help spot ANOMALIES in real DATA once it's
extracted from Xero -- the other half of Mercury's "AI can assist in test
case generation and data verification".

What this does NOT do: replace deterministic data quality checks. The dbt
tests / Great Expectations checks in the data pipeline project (completeness,
uniqueness, validity) are the authoritative, repeatable pass/fail gate --
they don't need an AI call and shouldn't depend on one for correctness.

What this DOES do: take a batch of records that already passed the
deterministic checks, and ask an AI model to look for softer, harder-to-rule-
based anomalies a human reviewer might flag -- e.g. a contact name that looks
like a typo of another contact's name, an invoice description that doesn't
match its account code, amounts that are individually valid but collectively
look like a duplicate entered twice with slightly different wording. This is
explicitly a second-pass, advisory check for a human to look at -- not an
automated gate that blocks or approves data on its own.
"""
import json
import os

import requests

PROMPT_TEMPLATE = """\
You are assisting a QA engineer with a second-pass review of financial
records that have already passed automated data quality checks
(completeness, uniqueness, validity). Look for softer anomalies a
rule-based check would miss: near-duplicate contact names, descriptions
that seem mismatched to their account code, or amounts that look like an
accidental duplicate entry rather than two genuine transactions.

For each anomaly you find, state: which records are involved, why it looks
suspicious, and how confident you are (this is advisory for a human
reviewer, not a verdict). If you find nothing suspicious, say so plainly --
do not invent an anomaly to seem useful.

Records:
{records_json}
"""


def verify_records(records: list[dict]) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Set ANTHROPIC_API_KEY to run AI-assisted verification.")

    prompt = PROMPT_TEMPLATE.format(records_json=json.dumps(records, indent=2))

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


# Example usage with intentionally suspicious sample data, so this script's
# output is checkable without needing a live Xero pull first.
SAMPLE_RECORDS = [
    {"contact": "Alice Smith", "description": "Office supplies", "account_code": "400", "amount": 120.00},
    {"contact": "Alice Smyth", "description": "Office supplies", "account_code": "400", "amount": 120.00},
    {"contact": "Bob Jones", "description": "Software license renewal", "account_code": "710", "amount": 4500.00},
    {"contact": "Carol Lee", "description": "Client lunch", "account_code": "200", "amount": 45.50},
]


if __name__ == "__main__":
    print("Running AI-assisted second-pass review on sample records...\n")
    result = verify_records(SAMPLE_RECORDS)
    print(result)
    print(
        "\n--- This is advisory output for a human reviewer. It does not "
        "replace the deterministic data quality tests in the pipeline. ---"
    )
