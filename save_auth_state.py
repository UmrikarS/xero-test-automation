"""
One-time manual login -> saved session state.

Run this yourself, once, whenever you need a fresh authenticated session:

    python save_auth_state.py

It opens a REAL, visible browser window (not headless). Log in manually,
including completing the MFA step from your authenticator app -- Playwright
cannot do that part for you, and this script doesn't try to. Once you land
on the dashboard, come back to the terminal and press Enter. The script
then saves your browser's cookies and local storage to auth_state.json.

Every other test in tests/ui/ loads that file instead of logging in from
scratch, so MFA only has to happen here, manually, not on every test run.

auth_state.json contains live session credentials -- it is already excluded
in .gitignore. Never commit it.

When you'll need to re-run this: Xero session cookies eventually expire
(exact duration varies). If tests/ui suddenly start failing with "not
logged in" style errors, that's the signal to run this script again.

IMPORTANT -- "Access Denied" when this script opens the browser:
This is bot detection (very likely Cloudflare or similar), not a real
login failure -- it can trigger purely from technical signals like
navigator.webdriver being true, regardless of a real human typing
credentials into the window. Fixed below two ways:
1. channel="chrome" launches your actual installed Google Chrome instead
   of Playwright's bundled Chromium -- run `playwright install chrome`
   once if that's not already installed.
2. args=["--disable-blink-features=AutomationControlled"] suppresses one
   of the most common automation fingerprints sites check for.
If Access Denied still happens after this, the fallback is logging in with
your completely normal, non-automated Chrome browser, exporting cookies
with a browser extension (e.g. "Cookie-Editor"), and hand-converting them
into Playwright's storage_state JSON shape -- ask for help with that
conversion if it comes to it, rather than fighting the automated-browser
approach further.

Alternative for full CI automation (not implemented here): if you need
tests/ui to run completely unattended in CI (this project's schedule job
currently expects a manually-refreshed auth_state.json instead), Xero's
authenticator setup shows a "manual entry key" as an alternative to
scanning the QR code -- save that secret, then use the `pyotp` library
(`pip install pyotp`) to generate a valid 6-digit code on demand:

    import pyotp
    totp = pyotp.TOTP("YOUR_SAVED_SECRET_KEY")
    current_code = totp.now()  # same code your authenticator app would show

That code could then be typed into pages/login_page.py's flow the same way
email/password are, giving a fully scripted login. Not wired up in this
project since it requires a secret specific to your own MFA enrollment
that can't be generated or guessed on your behalf.
"""

from playwright.sync_api import sync_playwright
import os


def main():
    with sync_playwright() as p:
        # This will create a real user profile folder locally
        user_data_dir = os.path.join(os.getcwd(), "chrome_profile")

        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1920, "height": 1080}
        )

        page = context.new_page()
        page.goto("https://login.xero.com/identity/user/login")

        input("Log in manually, then press Enter here to save your storage state...")

        context.storage_state(path="auth_state.json")
        context.close()


if __name__ == "__main__":
    main()

# from playwright.sync_api import sync_playwright
#
# AUTH_STATE_PATH = "auth_state.json"
#
#
# def main():
#     with sync_playwright() as p:
#         browser = p.chromium.launch(
#             headless=False,
#             channel="chrome",
#             args=["--disable-blink-features=AutomationControlled"],
#         )
#         page = browser.new_page()
#         page.goto("https://login.xero.com/identity/user/login")
#
#         print("\nA browser window has opened.")
#         print("Log in manually, including the MFA code from your authenticator app.")
#         print("Once you see the Xero dashboard, come back here and press Enter.\n")
#         input("Press Enter once you're logged in and on the dashboard...")
#
#         browser.contexts[0].storage_state(path=AUTH_STATE_PATH)
#         print(f"\nSaved authenticated session to {AUTH_STATE_PATH}")
#         print("tests/ui/ will now reuse this session instead of logging in from scratch.")
#
#         browser.close()
#
#
# if __name__ == "__main__":
#     main()
