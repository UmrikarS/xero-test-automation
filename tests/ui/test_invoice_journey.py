"""
UI test suite -- full journey: login -> create invoice -> reconcile -> report.

Authentication: Xero enforces MFA on login, which Playwright cannot complete
unattended (it needs a live 6-digit code from an authenticator app). Rather
than scripting the login form directly, these tests load a session that was
authenticated manually once via save_auth_state.py (see that file's
docstring) -- MFA happens there, one time, by a human; the tests here just
reuse the resulting session. If tests start failing with "not logged in"
style errors, re-run save_auth_state.py to refresh the session.

These tests are NOT run as part of every CI push (see
.github/workflows/tests.yml), only on a schedule, out of respect for Xero's
usage limits and because UI interaction is inherently slower/flakier than
API calls.

Concept demonstrated: equivalence partitioning applied to a UI form (same
technique as the API layer, different surface), and a UI-to-data
reconciliation check -- verifying a number rendered in the UI matches an
independently-computed expected value, rather than trusting the UI's own
arithmetic.
"""
import os

import pytest
from playwright.sync_api import sync_playwright

from pages.invoice_page import InvoicePage
from pages.reconciliation_page import ReconciliationPage
from pages.reports_page import ReportsPage

AUTH_STATE_PATH = "auth_state.json"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def authenticated_page(browser):
    if not os.path.exists(AUTH_STATE_PATH):
        pytest.skip(
            f"{AUTH_STATE_PATH} not found. Run `python save_auth_state.py` once, "
            f"logging in manually (including MFA), before running UI tests."
        )
    context = browser.new_context(storage_state=AUTH_STATE_PATH)
    page = context.new_page()
    page.goto("https://go.xero.com/Dashboard")
    if "login" in page.url:
        # A real test run confirmed this happens as sessions naturally
        # expire over time -- not a code bug, just expected maintenance.
        # Using skip() rather than assert here means every test in the
        # file reports one clean, short line each ("session expired,
        # re-run save_auth_state.py") instead of the full OAuth redirect
        # URL's stack trace repeated once per test.
        context.close()
        pytest.skip(
            "Saved session has expired or is invalid -- re-run "
            "`python save_auth_state.py` to log in again (including MFA) "
            "and refresh auth_state.json."
        )
    yield page
    context.close()


@pytest.mark.ui
class TestSessionLoads:
    def test_saved_session_reaches_dashboard(self, authenticated_page):
        """Confirms the session saved by save_auth_state.py is still valid
        and lands on the dashboard -- not a login-form test, since MFA
        makes scripting the login form itself impractical to run unattended."""
        assert "go.xero.com" in authenticated_page.url


@pytest.mark.ui
class TestInvoiceCreationJourney:

    @pytest.mark.parametrize(
        "quantity,unit_amount,should_succeed",
        [
            pytest.param(1, 100.00, True, id="valid-typical-invoice"),
            pytest.param(1, 0.01, True, id="smallest-valid-amount-boundary"),
            pytest.param(1, 0.00, False, id="zero-amount-boundary-rejected"),
            pytest.param(-1, 100.00, False, id="negative-quantity-rejected"),
        ],
    )
    def test_invoice_form_validates_amount_partitions(
        self, authenticated_page, unique_contact_name, quantity, unit_amount, should_succeed
    ):
        invoice_page = InvoicePage(authenticated_page)
        invoice_page.open_new_invoice()
        invoice_page.fill_invoice(
            contact=unique_contact_name,
            description="Automation test line item",
            quantity=quantity,
            unit_amount=unit_amount,
        )
        invoice_page.save()

        if should_succeed:
            assert not invoice_page.has_validation_error()
        else:
            assert invoice_page.has_validation_error()

    def test_create_and_approve_invoice_updates_status(self, authenticated_page, unique_contact_name):
        invoice_page = InvoicePage(authenticated_page)
        invoice_page.open_new_invoice()
        invoice_page.fill_invoice(unique_contact_name, "Automation test", 1, 100.00)
        invoice_page.save()
        assert invoice_page.get_status().strip().lower() == "draft"

        invoice_page.approve()
        assert invoice_page.get_status().strip().lower() == "awaiting payment"

    def test_void_invoice_updates_status(self, authenticated_page, unique_contact_name):
        invoice_page = InvoicePage(authenticated_page)
        invoice_page.open_new_invoice()
        invoice_page.fill_invoice(unique_contact_name, "Automation test", 1, 100.00)
        invoice_page.save()
        invoice_page.void()
        assert invoice_page.get_status().strip().lower() == "voided"


@pytest.mark.ui
class TestReconciliationJourney:
    @pytest.mark.skip(
        reason="Test design flaw, not a locator bug: this test looks for a bank "
               "transaction matching unique_invoice_reference, a string this suite "
               "generates itself -- nothing anywhere creates a real bank transaction "
               "with that reference, so no matching row can ever exist to find. A "
               "real test run confirmed this (timeout waiting for the row, not a "
               "wrong-selector error). Correct redesign: use api_client to fetch an "
               "existing unreconciled bank transaction from the Demo Company "
               "(GET /BankTransactions, or the statement-line data reconciliation "
               "actually matches against), create/select an invoice with the same "
               "amount, and match those two real records in the UI -- rather than "
               "inventing a reference and hoping a row appears for it."
    )
    def test_matching_bank_transaction_reconciles(self, authenticated_page, unique_invoice_reference):
        reconciliation_page = ReconciliationPage(authenticated_page)
        reconciliation_page.open()
        reconciliation_page.match_transaction(unique_invoice_reference)
        assert reconciliation_page.is_transaction_reconciled(unique_invoice_reference)


@pytest.mark.ui
class TestReportsJourney:
    def test_aged_receivables_total_matches_independently_calculated_total(self, authenticated_page, api_client):
        """
        UI-to-data reconciliation test: the number Xero's report page
        displays must match a total computed independently via the API,
        not just "look plausible". This is the same principle a data QA
        engineer applies when validating a BI dashboard number against the
        underlying warehouse query -- don't trust the presentation layer's
        own arithmetic.
        """
        # Independently compute the expected total from the API layer
        response = api_client.list_invoices(where='Status=="AUTHORISED"')
        invoices = response.json().get("Invoices", [])
        expected_total = round(sum(inv["AmountDue"] for inv in invoices), 2)

        reports_page = ReportsPage(authenticated_page)
        reports_page.open_aged_receivables()
        displayed_total = reports_page.get_total_due()

        assert displayed_total == expected_total, (
            f"Report shows {displayed_total} but API-computed total is {expected_total}"
        )
