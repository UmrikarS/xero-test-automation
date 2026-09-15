"""
Xero API client wrapper (real API, Demo Company, via Custom Connection).

Concept demonstrated: separating "how to call the API" from "what the test
asserts" -- the same separation-of-concerns idea as Page Object Model,
applied to API tests. Tests read like business scenarios, not raw
requests.calls, and if Xero ever changes an endpoint path or header, there's
exactly one place to fix it.

Note: no Xero-Tenant-Id header is needed here. That header exists for the
standard Authorization Code flow, where one app can be connected to multiple
organisations and needs to say which one each call is for. A Custom
Connection is scoped to exactly one organisation at creation time, so every
request implicitly targets that org already.
"""
import datetime

import requests

from utils.xero_auth import XeroTokenManager

BASE_URL = "https://api.xero.com/api.xro/2.0"


class XeroAPIClient:
    def __init__(self, token_manager: XeroTokenManager = None):
        self.token_manager = token_manager or XeroTokenManager()

    def _headers(self):
        return self.token_manager.get_headers()

    # ---- Invoices ----

    def create_invoice(self, invoice_type, contact_name, line_items, status=None, due_in_days=14):
        """
        status=None leaves Xero's default (DRAFT) in place. Pass
        status="AUTHORISED" when a test needs an invoice that can later be
        voided -- Xero only allows voiding AUTHORISED/SUBMITTED invoices;
        a DRAFT invoice must be deleted instead (see delete_invoice below).
        This distinction was discovered by test_void_invoice_changes_status
        failing with a 400 against a DRAFT invoice.

        DueDate is always sent, not just when authorising. Discovered
        requirement: Xero rejects an AUTHORISED invoice with
        "The document DueDate field must be specified" if it's missing --
        DRAFT invoices tolerate its absence, but always sending a real date
        avoids the inconsistency depending on which status is requested.
        """
        today = datetime.date.today()
        payload = {
            "Type": invoice_type,
            "Contact": {"Name": contact_name},
            "LineItems": line_items,
            "Date": today.isoformat(),
            "DueDate": (today + datetime.timedelta(days=due_in_days)).isoformat(),
        }
        if status:
            payload["Status"] = status
        return requests.post(f"{BASE_URL}/Invoices", json={"Invoices": [payload]}, headers=self._headers())

    def get_invoice(self, invoice_id):
        return requests.get(f"{BASE_URL}/Invoices/{invoice_id}", headers=self._headers())

    def authorise_invoice(self, invoice_id):
        payload = {"Invoices": [{"InvoiceID": invoice_id, "Status": "AUTHORISED"}]}
        return requests.post(f"{BASE_URL}/Invoices", json=payload, headers=self._headers())

    def void_invoice(self, invoice_id):
        """Only works on an AUTHORISED or SUBMITTED invoice. Returns 400
        against a DRAFT invoice -- use delete_invoice for those instead."""
        payload = {"Invoices": [{"InvoiceID": invoice_id, "Status": "VOIDED"}]}
        return requests.post(f"{BASE_URL}/Invoices", json=payload, headers=self._headers())

    def delete_invoice(self, invoice_id):
        """Only works on a DRAFT invoice. This is Xero's equivalent of
        void_invoice for invoices that were never authorised."""
        payload = {"Invoices": [{"InvoiceID": invoice_id, "Status": "DELETED"}]}
        return requests.post(f"{BASE_URL}/Invoices", json=payload, headers=self._headers())

    def list_invoices(self, where=None):
        params = {"where": where} if where else {}
        return requests.get(f"{BASE_URL}/Invoices", headers=self._headers(), params=params)

    # ---- Contacts ----

    def create_contact(self, name):
        payload = {"Contacts": [{"Name": name}]}
        return requests.post(f"{BASE_URL}/Contacts", json=payload, headers=self._headers())

    def find_contact_by_name(self, name):
        return requests.get(
            f"{BASE_URL}/Contacts",
            headers=self._headers(),
            params={"where": f'Name=="{name}"'},
        )

    def archive_contact(self, contact_id):
        """Xero has no hard delete for Contacts -- archiving is the closest
        equivalent and is what test cleanup should do."""
        payload = {"Contacts": [{"ContactID": contact_id, "ContactStatus": "ARCHIVED"}]}
        return requests.post(f"{BASE_URL}/Contacts", json=payload, headers=self._headers())

    # ---- Bank transactions / reconciliation ----

    def list_bank_transactions(self, where=None):
        params = {"where": where} if where else {}
        return requests.get(f"{BASE_URL}/BankTransactions", headers=self._headers(), params=params)
