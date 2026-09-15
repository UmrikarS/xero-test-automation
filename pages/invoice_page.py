# """
# Invoice Page Object.
#
# The "New invoice" button used here was discovered directly from a real test
# run's failure output, not guessed: an earlier version tried
# get_by_role("button", name="New"), which raised a Playwright strict-mode
# violation because Playwright's default substring, case-insensitive matching
# made "New" match TWO different elements on the dashboard --
# aria-label="Create new" (a dropdown menu trigger) and a widget's
# <a role="button">New invoice</a> (a direct one-click shortcut). Playwright's
# own error message listed both elements verbatim, including their exact
# accessible names -- that's how "New invoice" (exact) was identified as the
# simpler, single-click path, avoiding the dropdown-then-menuitem approach
# entirely (which separately timed out waiting for a "menuitem" named
# "Invoice" that may not exist under that name, or may be nested under a
# submenu).
#
# Lesson: a Playwright strict-mode violation error is not just a failure to
# fix -- it's often handing you the real DOM structure for free. Read it
# before guessing a different selector.
#
# Locators are best-effort placeholders -- verify against the real Demo
# Company with `playwright codegen --load-storage=auth_state.json
# https://go.xero.com/Dashboard` before first run (see root README for why
# --load-storage matters), and update the selectors below to match what it
# records if your Demo Company's UI differs.
# """
# from .base_page import BasePage
#
#
# class InvoicePage(BasePage):
#     DASHBOARD_URL = "https://xero.com"
#
#     def __init__(self, page):
#         super().__init__(page)
#
#         # Navigation & Header Controls
#         self.new_invoice_btn = page.get_by_role("button", name="New invoice")
#
#         # Primary Form Fields
#         self.contact_field = page.get_by_label("Contact", exact=True)
#         self.issue_date_field = page.get_by_label("Issue date", exact=True)
#         self.due_date_field = page.get_by_label("Due date", exact=True)
#         self.invoice_number_field = page.get_by_label("Invoice number", exact=True)
#         self.reference_field = page.get_by_label("Reference", exact=True)
#
#         # Contact Dropdown Interaction
#         self.add_contact_dropdown_btn = page.get_by_role("button", name="Add", exact=True)
#
#         # Line Items Grid Layout Containers
#         # Locates the main scrollable grid or table container holding the line items
#         self.items_grid_scroll_container = page.locator(".x-grid-scroll-body, [role='grid'], table").first
#
#         # Target the first data row inside the line items table
#         self.first_row = page.locator("tbody tr, [role='row']").nth(1)  # nth(0) is usually the header row
#
#         # Row-scoped relative inputs (safer than global placeholders when multiple rows exist)
#         self.description_field = self.first_row.get_by_placeholder("Description")
#         self.quantity_field = self.first_row.get_by_placeholder("Qty")
#         self.unit_amount_field = self.first_row.get_by_placeholder("Price")
#         self.discount_field = self.first_row.get_by_placeholder("Disc. %")
#
#         # Footer Action Buttons
#         self.save_btn = page.get_by_role("button", name="Save", exact=True)
#         self.approve_btn = page.get_by_role("button", name="Approve", exact=True)
#         self.void_btn = page.get_by_role("button", name="Void", exact=True)
#
#         # Feedback & Validation
#         self.status_badge = page.locator("[data-automation-id='invoice-status']")
#         self.validation_error = page.locator(".validation-summary-errors, [role='alert']")
#
#     def open_new_invoice(self):
#         self.goto(self.DASHBOARD_URL)
#         self.wait_for_load()
#         self.new_invoice_btn.click()
#         self.wait_for_load()
#
#     def fill_invoice(self, contact, description, quantity, unit_amount):
#         """
#         Fills out the invoice details. Handles horizontal scrolling for hidden fields
#         and explicit contact selection.
#         """
#         # 1. Handle Contact Dropdown
#         self.contact_field.click()
#         self.contact_field.fill(contact)
#
#         if self.add_contact_dropdown_btn.is_visible():
#             self.add_contact_dropdown_btn.click()
#         else:
#             self.contact_field.press("Enter")
#
#         # 2. Scroll Left to expose Description and Qty if they are hidden
#         # Playwright's click() automatically scrolls elements into view vertically,
#         # but horizontal grid components sometimes require explicit focus or scrolling evaluation.
#         if self.items_grid_scroll_container.is_visible():
#             self.items_grid_scroll_container.evaluate("el => el.scrollLeft = 0")
#
#         # 3. Populate Line Items (Scoped directly to the specific row to prevent multi-element exceptions)
#         if description:
#             self.description_field.scroll_into_view_if_needed()
#             self.description_field.fill(description)
#
#         if quantity:
#             self.quantity_field.scroll_into_view_if_needed()
#             self.quantity_field.fill(str(quantity))
#
#         if unit_amount:
#             self.unit_amount_field.scroll_into_view_if_needed()
#             self.unit_amount_field.fill(str(unit_amount))
#
#     def save(self):
#         self.save_btn.click()
#         self.wait_for_load()
#
#     def approve(self):
#         self.approve_btn.click()
#         self.wait_for_load()
#
#     def void(self):
#         self.void_btn.click()
#         self.wait_for_load()
#
#     def get_status(self) -> str:
#         return self.status_badge.inner_text()
#
#     def has_validation_error(self) -> bool:
#         return self.validation_error.is_visible()
#
#     def get_validation_error_text(self) -> str:
#         return self.validation_error.inner_text()


from .base_page import BasePage


class InvoicePage(BasePage):
    DASHBOARD_URL = "https://go.xero.com/app/!zq!J8/homepage"

    def __init__(self, page):
        super().__init__(page)

        # Navigation & Header Controls
        self.new_invoice_btn = page.get_by_role("button", name="New invoice")

        # Primary Form Fields
        # Codegen revealed this field does not have a visible text string label
        self.contact_field = page.get_by_label("", exact=True)
        self.due_date_field = page.get_by_label("Due date")
        self.due_date_year_select = page.get_by_label("Select year")

        # Line Items Grid Locators
        # Targeting by row container mapping allows reliable scoped fills
        self.grid_row = page.get_by_role("row", name="Drag handle Item Description", exact=False)
        self.description_field = page.get_by_label("Description")
        self.quantity_field = self.grid_row.get_by_label("Qty.")
        self.unit_amount_field = page.get_by_label("Price")

        # Save & Approval Workflow Controls
        self.more_save_options_btn = page.get_by_label("More save options")
        self.submit_for_approval_btn = page.get_by_role("button", name="Submit for approval")
        self.awaiting_approval_tab = page.get_by_role("link", name="Awaiting Approval", exact=False)

        # Legacy/Alternative approvals (keeping dynamic backups fallback)
        self.approve_link = page.get_by_role("link", name="Approve", exact=True)
        self.confirm_ok_btn = page.get_by_role("link", name="OK", exact=True)

        # Status Notification Alerts
        self.toast_notification = page.get_by_text("item was approved", exact=False)

    def open_new_invoice(self):
        self.goto(self.DASHBOARD_URL)
        self.wait_for_load()
        self.new_invoice_btn.click()
        self.wait_for_load()

    def fill_invoice(self, contact, description, quantity, unit_amount, due_date_label=None):
        """
        Fills out the invoice form fields strictly following the recorded codegen sequence.
        """
        # 1. Select Contact
        self.contact_field.click()
        self.contact_field.fill(contact)
        self.page.get_by_role("button", name=contact, exact=False).click()

        # 2. Select Due Date (Optional helper if a specific calendar cell label string is supplied)
        if due_date_label:
            self.due_date_field.click()
            self.due_date_year_select.select_option("2027")
            self.page.get_by_label(due_date_label).click()

        # 3. Populate Grid Line Items
        self.description_field.click()
        self.description_field.fill(description)

        self.quantity_field.click()
        self.quantity_field.fill(str(quantity))

        self.unit_amount_field.click()
        self.unit_amount_field.fill(str(unit_amount))

    def submit_for_approval(self):
        """
        Executes the two-step click workflow to submit an invoice.
        """
        self.more_save_options_btn.click()
        self.submit_for_approval_btn.click()
        self.wait_for_load()

    def approve_from_awaiting_tab(self):
        """
        Navigates to the approval list view and processes the invoice confirmation alert.
        """
        self.awaiting_approval_tab.click()
        self.wait_for_load()
        self.approve_link.click()
        self.confirm_ok_btn.click()
        self.wait_for_load()

    def verify_approved_status(self) -> bool:
        """
        Returns true if the approval toast banner or confirmation confirmation text appears.
        """
        return self.toast_notification.first.is_visible()



