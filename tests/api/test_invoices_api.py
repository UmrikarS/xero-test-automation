"""
API test layer for the Invoices/Contacts resources -- runs against the real
Xero API, authorized against your Demo Company (see .env.example for setup).

Concept demonstrated: equivalence partitioning + boundary value analysis
(ISTQB). For UnitAmount, the valid equivalence class is "positive number".
The invalid equivalence classes are "zero" and "negative number". Zero is
also the BOUNDARY between valid and invalid -- that's why it gets its own
test case rather than being lumped in with "any negative number". We don't
test every possible amount; we test one representative from each partition
plus the boundary, which is the point of the technique.

Note on live-API testing: these tests hit real rate-limited infrastructure,
so each test creates the minimum data needed, and cleanup fixtures
(cleanup_contacts / cleanup_invoices) archive or void everything created,
regardless of pass/fail, so repeated CI runs don't pollute the Demo Company.
"""
import pytest


def _line_item(amount, account_code="200"):
    # TaxType "NONE" avoids Xero automatically calculating sales tax on top
    # of UnitAmount -- without this, Total != sum(UnitAmount) even though
    # nothing is wrong, because tax gets added on top. See
    # test_created_invoice_total_matches_line_items for why this matters.
    return [{
        "Description": "Automation test item",
        "Quantity": 1,
        "UnitAmount": amount,
        "AccountCode": account_code,
        "TaxType": "NONE",
    }]


@pytest.mark.api
class TestInvoiceCreationBoundaries:

    @pytest.mark.parametrize(
        "amount,expect_success,partition",
        [
            pytest.param(100.00, True, "valid-typical", id="valid-typical-amount"),
            pytest.param(0.01, True, "valid-boundary-low", id="smallest-valid-amount"),
            pytest.param(
                0.00, False, "invalid-boundary",
                id="zero-amount-boundary",
                marks=pytest.mark.xfail(
                    reason="FINDING (verified against real Xero API, 2026-09): Xero's "
                           "Invoices endpoint does NOT reject a zero UnitAmount -- it "
                           "silently accepts it and creates a $0 invoice with no "
                           "ValidationErrors. Our assumption that Xero enforces "
                           "'amount must be positive' at the API layer was wrong. "
                           "Documented here as a data-quality risk (zero-value invoices "
                           "can be created without any server-side guard) rather than "
                           "silently changed to expect success, so this gap stays visible "
                           "in test output instead of disappearing.",
                    strict=True,
                ),
            ),
            pytest.param(
                -50.00, False, "invalid-negative",
                id="negative-amount",
                marks=pytest.mark.xfail(
                    reason="FINDING (verified against real Xero API, 2026-09): Xero "
                           "accepted a negative UnitAmount outright, producing an "
                           "invoice with Total=-54.13 (tax was even calculated on the "
                           "negative value). No client-side validation exists to catch "
                           "this before it reaches Xero either. Flagged as a real "
                           "data-quality/input-validation gap, not silently accepted "
                           "as 'expected' behaviour.",
                    strict=True,
                ),
            ),
        ],
    )
    def test_invoice_amount_partitions(
        self, api_client, unique_contact_name, cleanup_invoices, amount, expect_success, partition
    ):
        response = api_client.create_invoice(
            invoice_type="ACCREC",
            contact_name=unique_contact_name,
            line_items=_line_item(amount),
        )
        body = response.json()

        # Register for cleanup regardless of expected outcome -- Xero may
        # create an invoice (200) even on a case we expected to be rejected
        # (see the xfail findings above), and an invoice that actually got
        # created still needs to be cleaned up either way.
        if response.status_code == 200 and body.get("Invoices"):
            cleanup_invoices.append(body["Invoices"][0]["InvoiceID"])

        if expect_success:
            assert response.status_code == 200, (
                f"Partition '{partition}' (amount={amount}) expected to succeed, "
                f"got {response.status_code}: {body}"
            )
        else:
            # Xero returns 200 with an ElementValidationErrors block for some
            # invalid payloads rather than an HTTP 4xx -- check both shapes.
            has_validation_error = response.status_code == 400 or any(
                "ValidationErrors" in inv for inv in body.get("Invoices", [])
            )
            assert has_validation_error, (
                f"Partition '{partition}' (amount={amount}) expected a validation "
                f"error, got {response.status_code}: {body}"
            )

    def test_amount_with_excess_decimal_precision_is_rounded_not_rejected(
        self, api_client, unique_contact_name, cleanup_invoices
    ):
        """
        Automates a finding first discovered through manual UI testing:
        entering an amount with more than 2 decimal places (e.g. 10.99999)
        doesn't get rejected or truncated -- Xero rounds it to the nearest
        cent (round-half-up), same as standard currency rounding. This test
        confirms the same rule holds at the API layer, not just in the UI,
        by reading back the actual stored UnitAmount rather than just
        checking the request was accepted.
        """
        response = api_client.create_invoice(
            invoice_type="ACCREC",
            contact_name=unique_contact_name,
            line_items=_line_item(10.99999),
        )
        assert response.status_code == 200, response.text
        invoice = response.json()["Invoices"][0]
        cleanup_invoices.append(invoice["InvoiceID"])

        stored_amount = invoice["LineItems"][0]["UnitAmount"]
        assert stored_amount == 11.00, (
            f"Expected 10.99999 to be rounded to 11.00, but Xero stored it as "
            f"{stored_amount} -- rounding rule may differ from what was "
            f"observed manually in the UI."
        )

    def test_created_invoice_total_matches_line_items(self, api_client, unique_contact_name, cleanup_invoices):
        """Contract test: the API's computed Total must equal the sum of line
        items. This is a data-quality assertion, not just an HTTP-status check.

        TaxType "NONE" is required here -- without it, Xero automatically
        calculates sales tax on top of the line item amounts (a real
        behaviour discovered by this test originally failing with
        Total=162.38 instead of the expected 150.00). That's correct Xero
        behaviour, not a bug -- this test is specifically checking the
        no-tax case, and a separate test would be needed to verify tax
        calculation itself if that becomes in scope."""
        line_items = [
            {"Description": "Item A", "Quantity": 1, "UnitAmount": 100.00, "AccountCode": "200", "TaxType": "NONE"},
            {"Description": "Item B", "Quantity": 1, "UnitAmount": 50.00, "AccountCode": "200", "TaxType": "NONE"},
        ]
        response = api_client.create_invoice("ACCREC", unique_contact_name, line_items)
        assert response.status_code == 200, response.text
        invoice = response.json()["Invoices"][0]
        cleanup_invoices.append(invoice["InvoiceID"])

        assert invoice["Total"] == 150.00


@pytest.mark.api
class TestInvoiceLifecycle:

    def test_void_invoice_changes_status(self, api_client, unique_contact_name):
        """
        Must create the invoice as AUTHORISED, not the default DRAFT --
        Xero rejects void_invoice against a DRAFT invoice with a 400
        (discovered by this test originally failing that way). Voiding is
        specifically an AUTHORISED/SUBMITTED -> VOIDED transition; a DRAFT
        invoice must be deleted instead (see delete_invoice).

        Second discovery along the way: authorising an invoice without a
        DueDate fails validation ("The document DueDate field must be
        specified") even though DRAFT invoices tolerate its absence fine.
        Fixed in api_client.create_invoice, which now always sends a real
        Date/DueDate regardless of status.
        """
        create_resp = api_client.create_invoice(
            "ACCREC", unique_contact_name, _line_item(100.00), status="AUTHORISED"
        )
        assert create_resp.status_code == 200, create_resp.text
        invoice_id = create_resp.json()["Invoices"][0]["InvoiceID"]

        void_resp = api_client.void_invoice(invoice_id)
        assert void_resp.status_code == 200, void_resp.text
        assert void_resp.json()["Invoices"][0]["Status"] == "VOIDED"
        # No cleanup fixture needed here -- voiding IS the cleanup.

    def test_get_nonexistent_invoice_returns_error(self, api_client):
        response = api_client.get_invoice("00000000-0000-0000-0000-000000000000")
        assert response.status_code in (400, 404)


@pytest.mark.api
class TestContactDataQuality:
    """Maps to the data-quality dimension: uniqueness."""

    def test_contact_created_and_discoverable_by_name(self, api_client, unique_contact_name, cleanup_contacts):
        create_resp = api_client.create_contact(unique_contact_name)
        assert create_resp.status_code == 200, create_resp.text
        contact_id = create_resp.json()["Contacts"][0]["ContactID"]
        cleanup_contacts.append(contact_id)

        find_resp = api_client.find_contact_by_name(unique_contact_name)
        assert find_resp.status_code == 200
        found = find_resp.json()["Contacts"]
        assert len(found) == 1, "Expected exactly one contact matching the unique test name"

    def test_empty_contact_name_rejected(self, api_client):
        response = api_client.create_contact("")
        body = response.json()
        has_validation_error = response.status_code == 400 or any(
            "ValidationErrors" in c for c in body.get("Contacts", [])
        )
        assert has_validation_error, "Empty name should violate completeness rule"
