"""
Reports Page Object -- Aged Receivables report.

IMPORTANT: same caveat as reconciliation_page.py and invoice_page.py -- the
original direct-URL approach here was a guess, never verified live, and
Xero's reports are commonly accessed through a searchable Reports menu
rather than a fixed reportId query string that's guaranteed stable across
UI versions. Fixed by navigating through the Reports section's own search,
the same way a user would find "Aged Receivables Summary" by typing its
name rather than remembering a URL.

Locators are STILL UNVERIFIED against a real session. A real test run
confirmed the "Search reports" placeholder is simply wrong -- not
imprecise, wrong: it timed out with ZERO matches, meaning no element with
that placeholder exists at all (a strict-mode violation with multiple
false-positive matches, like "New" and "To" elsewhere in this project,
would look different -- this is a genuine miss, not an ambiguity problem).
Do not guess a third placeholder string blindly. Verify with:
    playwright codegen --load-storage=auth_state.json https://go.xero.com/Reports
(loading your saved session avoids the login-page bot-detection block --
see the root README for why --load-storage matters). Click through
Reports -> search "Aged Receivables" -> open the report exactly as a human
would, and replace BOTH locators below with what it records.
"""
from .base_page import BasePage


class ReportsPage(BasePage):
    REPORTS_URL = "https://go.xero.com/Reports"

    def __init__(self, page):
        super().__init__(page)
        self.report_search_field = page.get_by_placeholder("Search reports")
        self.aged_receivables_link = page.get_by_role("link", name="Aged Receivables Summary")
        self.total_due_cell = page.locator("[data-automation-id='report-total-due']")

    def open_aged_receivables(self):
        """
        Navigates via the Reports section's search rather than a direct
        URL -- see this file's module docstring for why a hardcoded
        reportId query string is unreliable here.
        """
        self.goto(self.REPORTS_URL)
        self.wait_for_load()
        self.report_search_field.fill("Aged Receivables")
        self.aged_receivables_link.click()
        self.wait_for_load()

    def get_total_due(self) -> float:
        text = self.total_due_cell.inner_text()
        return float(text.replace("$", "").replace(",", "").strip())
