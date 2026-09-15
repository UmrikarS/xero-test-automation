"""
Shared fixtures for testing against the real Xero API (Demo Company).

Concept demonstrated: fixture scope AND test isolation against a live,
shared, stateful system that you don't control and can't reset between
tests.

- session-scoped: the token manager and API client. Getting an access token
  is a network call and tokens are valid for the whole session, so there is
  no correctness reason to recreate them per test -- only a
  performance/rate-limit reason to avoid recreating them.
- function-scoped + uuid-suffixed test data: since there is no "_reset"
  endpoint on a real system, isolation instead comes from (a) every test
  creating its own uniquely-named record so it can never collide with data
  left behind by a previous run, and (b) an explicit teardown that archives
  or voids whatever the test created, so the Demo Company doesn't
  accumulate junk data across repeated CI runs.
"""
import uuid

import pytest

from utils.api_client import XeroAPIClient
from utils.xero_auth import XeroTokenManager


@pytest.fixture(scope="session")
def token_manager():
    return XeroTokenManager()


@pytest.fixture(scope="session")
def api_client(token_manager):
    return XeroAPIClient(token_manager)


@pytest.fixture
def unique_contact_name():
    """UUID suffix guarantees no collision with real Demo Company contacts
    or with data left over from a previous/parallel test run."""
    return f"Automation Test Contact {uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_invoice_reference():
    return f"AUTOTEST-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_contacts(api_client):
    """
    Teardown fixture: tests register ContactIDs they created via
    cleanup_contacts.append(contact_id), and this fixture archives them
    after the test finishes -- pass or fail. Xero has no hard delete for
    Contacts, so archiving is the correct cleanup action.
    """
    created_ids = []
    yield created_ids
    for contact_id in created_ids:
        api_client.archive_contact(contact_id)


@pytest.fixture
def cleanup_invoices(api_client):
    """
    Teardown fixture: tests register InvoiceIDs they created via
    cleanup_invoices.append(invoice_id), and this fixture cleans them up
    after the test finishes -- pass or fail.

    Xero has two different cleanup actions depending on invoice status:
    void_invoice only works on AUTHORISED/SUBMITTED invoices; a DRAFT
    invoice (the default status when none is specified at creation) must
    be deleted instead, or void_invoice returns a 400. Since most tests in
    this suite create DRAFT invoices, this tries void first and falls back
    to delete -- discovered after cleanup was silently failing for every
    DRAFT invoice created by test_invoice_amount_partitions.
    """
    created_ids = []
    yield created_ids
    for invoice_id in created_ids:
        response = api_client.void_invoice(invoice_id)
        if response.status_code != 200:
            api_client.delete_invoice(invoice_id)
