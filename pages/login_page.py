"""
Login Page Object for the real Xero Demo Company.

NOT used by the active test suite. Xero enforces MFA on login, which this
page object cannot complete (it has no way to obtain a live 6-digit
authenticator code), so tests/ui/ uses a pre-authenticated saved session
instead (see save_auth_state.py). This file is kept as a reference
implementation of scripted login for accounts that don't have MFA enabled,
or as a starting point if you later add pyotp-based programmatic MFA (see
save_auth_state.py's docstring for that alternative).

IMPORTANT: the locators below are written using Playwright's recommended
role/label/text-based selectors (the most resilient approach, since they
don't depend on internal CSS class names that Xero can change at any time).
Verify the exact accessible names against the live login page before use --
easiest way is `playwright codegen https://login.xero.com`, which records
real selectors as you click through the flow by hand.
"""
from .base_page import BasePage


class LoginPage(BasePage):
    LOGIN_URL = "https://login.xero.com/identity/user/login"

    def __init__(self, page):
        super().__init__(page)
        self.email_field = page.get_by_label("Email address")
        self.password_field = page.get_by_label("Password")
        self.continue_btn = page.get_by_role("button", name="Log in")

    def login(self, email, password):
        self.goto(self.LOGIN_URL)
        self.email_field.fill(email)
        self.continue_btn.click()
        self.password_field.fill(password)
        self.continue_btn.click()
        self.wait_for_load()

    def is_logged_in(self) -> bool:
        # After login, Xero redirects to the organisation dashboard.
        return "dashboard" in self.page.url or "Dashboard" in self.page.title()
