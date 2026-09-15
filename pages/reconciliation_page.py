"""
Bank Reconciliation Page Object.

IMPORTANT: there is no stable static URL for this screen. Confirmed
directly: hovering the real Reconcile button previews a URL like
https://go.xero.com/BankRec/BankRec.aspx?accountId=562555f2-8cde-4ce9-8203-0363922537a4
-- Xero does have a real underlying URL, it just requires the
per-organisation, per-bank-account GUID, which is why a hardcoded static
path (e.g. /Bank/BankRec.aspx with no ID) never worked. The reliable way
in is to navigate the same way a user would: from the dashboard, into the
specific bank account's own "Reconcile" button.

CONFIRMED via `playwright codegen --load-storage=auth_state.json
https://go.xero.com/Dashboard` (previous version of this locator was an
unverified guess and timed out in a real test run):

- The element's accessible ROLE is "button", not "link" as originally
  guessed.
- The accessible NAME includes a live count, e.g. "Reconcile 20 items" --
  that count changes as the account gets reconciled, so matching the exact
  string would break the moment it does. Matched with a regex instead.
- The Demo Company's actual bank account name is "Business Bank Account",
  which happens to match this file's original default guess.

DEEPER PROBLEM, not fixable by a better locator: match_transaction() below
takes a transaction_ref and looks for a row matching it -- but a real test
run showed this timing out, and the reason isn't a wrong selector. Nothing
anywhere in this project ever creates a bank transaction with that
reference; it's a randomly generated string (see the unique_invoice_reference
fixture) with no corresponding row to find, by design of how that fixture
was reused here without checking whether it fit. Real bank reconciliation
matches an EXISTING bank statement line (commonly pre-seeded in a Demo
Company) against an existing invoice or transaction -- it is never matched
by an arbitrary string invented by the test itself. See
test_matching_bank_transaction_reconciles's skip reason in
test_invoice_journey.py for why this test is marked skip rather than kept
failing on a locator that can never succeed as currently designed, and what
a correct redesign would need to do instead.
"""
import re

from .base_page import BasePage


class ReconciliationPage(BasePage):
    DASHBOARD_URL = "https://go.xero.com/Dashboard"
    RECONCILE_BUTTON_PATTERN = re.compile(r"Reconcile \d+ items?", re.IGNORECASE)

    def __init__(self, page):
        super().__init__(page)
        # UNVERIFIED, and likely unfixable as designed -- see this file's
        # module docstring addition below and test_invoice_journey.py's
        # skip reason on test_matching_bank_transaction_reconciles for why.
        self.transaction_row = lambda ref: page.locator(f"[data-transaction-ref='{ref}']")
        # exact=True applied preemptively -- "OK" is exactly the kind of
        # short, generic name that already caused false-positive matches
        # twice elsewhere in this project ("New", "To").
        self.match_btn = page.get_by_role("button", name="OK", exact=True)
        self.reconciled_badge = page.locator("[data-automation-id='reconciled-status']")

    def open(self, bank_account_name="Business Bank Account"):
        """
        Navigates via the dashboard rather than a direct URL (see module
        docstring for why). Scopes to the specific account's card by
        finding the innermost container that has both the account name and
        a matching Reconcile button, so this still works correctly if a
        Demo Company ever has more than one bank account on the dashboard.
        """
        self.goto(self.DASHBOARD_URL)
        self.wait_for_load()
        reconcile_btn = self.page.get_by_role("button", name=self.RECONCILE_BUTTON_PATTERN)
        account_card = self.page.locator("*").filter(has_text=bank_account_name).filter(has=reconcile_btn)
        account_card.last.get_by_role("button", name=self.RECONCILE_BUTTON_PATTERN).click()
        self.wait_for_load()

    def match_transaction(self, transaction_ref):
        self.transaction_row(transaction_ref).click()
        self.match_btn.click()
        self.wait_for_load()

    def is_transaction_reconciled(self, transaction_ref) -> bool:
        return "Reconciled" in self.reconciled_badge.inner_text()
