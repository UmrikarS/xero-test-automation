"""
Tests generated from ai_assisted_testing/ai_generated_test_cases.json.

Concept demonstrated: AI-assisted test case generation, with the human
review step made visible in the test results themselves. Cases marked
"ambiguous" in the source file are not silently skipped or silently
asserted -- they show up in `pytest -v` output as explicitly skipped with
the exact reason recorded, so a reviewer scanning CI output can see
"these N cases need a real Xero run to resolve" rather than the ambiguity
disappearing into a JSON file nobody reads day-to-day.
"""
import json
from pathlib import Path

import pytest

CASES_PATH = Path(__file__).parent.parent.parent / "ai_assisted_testing" / "ai_generated_test_cases.json"


def _load_cases():
    with open(CASES_PATH) as f:
        return json.load(f)


def _line_item(amount):
    return [{"Description": "AI-generated case", "Quantity": 1, "UnitAmount": amount, "AccountCode": "200", "TaxType": "NONE"}]


DATA = _load_cases()


@pytest.mark.api
class TestAIGeneratedInvoiceAmountCases:

    @pytest.mark.parametrize(
        "case",
        DATA["invoice_amount_cases"],
        ids=[c["id"] for c in DATA["invoice_amount_cases"]],
    )
    def test_ai_suggested_amount_case(self, api_client, unique_contact_name, cleanup_invoices, case):
        if case["expect_success"] == "ambiguous":
            pytest.skip(
                f"AI-suggested case '{case['id']}' needs manual verification against "
                f"the real Xero Demo Company before it can be a hard assertion: "
                f"{case['review_note']}"
            )

        response = api_client.create_invoice(
            invoice_type="ACCREC",
            contact_name=unique_contact_name,
            line_items=_line_item(case["unit_amount"]),
        )
        body = response.json()

        if case["expect_success"]:
            assert response.status_code == 200, f"{case['id']}: {case['description']} -- {body}"
            cleanup_invoices.append(body["Invoices"][0]["InvoiceID"])
        else:
            has_error = response.status_code == 400 or any(
                "ValidationErrors" in inv for inv in body.get("Invoices", [])
            )
            assert has_error, f"{case['id']}: {case['description']} -- expected rejection, got {body}"


@pytest.mark.api
class TestAIGeneratedContactNameCases:

    @pytest.mark.parametrize(
        "case",
        DATA["contact_name_cases"],
        ids=[c["id"] for c in DATA["contact_name_cases"]],
    )
    def test_ai_suggested_contact_name_case(self, api_client, cleanup_contacts, case):
        if case["expect_rejected"] == "ambiguous":
            pytest.skip(
                f"AI-suggested case '{case['id']}' needs manual verification against "
                f"the real Xero Demo Company before it can be a hard assertion: "
                f"{case['review_note']}"
            )

        response = api_client.create_contact(case["name"])
        body = response.json()

        if case["expect_rejected"]:
            has_error = response.status_code == 400 or any(
                "ValidationErrors" in c for c in body.get("Contacts", [])
            )
            assert has_error, f"{case['id']}: {case['description']} -- expected rejection, got {body}"
        else:
            assert response.status_code == 200, f"{case['id']}: {case['description']} -- {body}"
            cleanup_contacts.append(body["Contacts"][0]["ContactID"])
