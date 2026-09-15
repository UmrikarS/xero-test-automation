# Xero Test Automation Project

A test automation suite covering three layers against the real **Xero Demo Company**:
UI automation (Playwright + POM), API testing (requests + Pytest), and a
security-flavoured SQL injection suite based on the OWASP SQL Injection
Prevention Cheat Sheet.

Built to demonstrate: Page Object Model, ISTQB test-design techniques
(equivalence partitioning, boundary value analysis), test isolation, data-driven
testing with `pytest.mark.parametrize`, and injection-defence understanding 
mapped against real QA/data-engineering job requirements.

## Project structure

```
xero-test-automation/
├── pages/                  # Page Object Model for the Xero UI
│   ├── base_page.py
│   ├── login_page.py
│   ├── invoice_page.py
│   ├── reconciliation_page.py
│   └── reports_page.py
├── tests/
│   ├── ui/                 # Playwright journey tests (login → invoice → reconcile → report)
│   ├── api/                # Requests + Pytest against the real Xero API
│   └── security/           # SQL injection suite (local vulnerable-vs-safe demo)
├── postman/                # Postman collection mirroring the API tests, for manual/exploratory testing
├── ai_assisted_testing/    # AI-assisted test case generation + data verification scripts
├── fixtures/conftest.py    # Shared fixtures: token manager, API client, test-data isolation
├── utils/
│   ├── xero_auth.py        # OAuth2 Custom Connection (client_credentials) token handling
│   └── api_client.py       # Xero API client wrapper
├── security_demo/app.py    # Local Flask+SQLite app: vulnerable vs parameterized endpoints
├── .github/workflows/tests.yml
├── .env.example
└── requirements.txt
```

## Setup

### 1. Install dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Get Xero API credentials - Custom Connection method
This project uses Xero's **Custom Connection** option rather than the standard
browser OAuth flow - it's built for exactly this single-organisation use case,
skips the browser login step entirely, needs no refresh token to manage, and
Xero explicitly allows it for free against the Demo Company.

1. Create a free Xero account and turn on the **Demo Company** (My Xero → Try the Demo Company).
2. Register an app at [developer.xero.com/app/manage](https://developer.xero.com/app/manage/), selecting **"Custom connection"** as the integration type.
3. Select scopes (`accounting.transactions`, `accounting.contacts`, `accounting.settings`) and authorise against your **Demo Company**.
4. Configuration tab → **Generate a secret**. Copy `.env.example` to `.env` and fill in `XERO_CLIENT_ID` and `XERO_CLIENT_SECRET` - that's the entire setup, no refresh token or tenant ID needed.

### 3. Authenticate for UI tests  save a session once (MFA workaround)
Xero enforces MFA on login, which Playwright can't complete unattended (no
way to obtain a live 6-digit authenticator code programmatically). Instead
of scripting the login form, log in manually **once**:
```bash
python save_auth_state.py
```
A real browser window opens  log in normally, including the MFA step from
your authenticator app, then press Enter in the terminal once you're on the
dashboard. This saves your session to `auth_state.json` (gitignored -
never commit it), which every UI test then reuses instead of logging in
from scratch. Re-run this script if UI tests start failing with
"not logged in" style errors  that means the saved session expired.

### 4. Verify Playwright locators before running UI tests
The Page Object locators in `pages/` are written using Playwright's
role/label-based selectors as best-effort placeholders. Before running the
UI suite, verify them against the real Demo Company UI - **load your saved
session into codegen rather than hitting the login page directly**:
```bash
playwright codegen --load-storage=auth_state.json https://go.xero.com/Dashboard
```
Pointing codegen at `https://login.xero.com` directly launches a fresh,
unauthenticated, automated browser - Xero's bot detection can flag and
block that (`Access Denied`), separately from the MFA problem. Loading
your existing `auth_state.json` starts codegen already logged in, skipping
the login page and its bot detection entirely.

**Important:** none of the page objects use a hardcoded direct URL to jump
straight to a specific screen (e.g. a specific bank account's reconcile
page, or a specific report). Xero generates per-organisation, per-account
IDs as part of those URLs, so a static link either 404s or redirects to the
dashboard - this was discovered directly (a guessed `/Bank/BankRec.aspx`
URL didn't work). Every page object instead navigates the same way a human
would: land on the dashboard or a menu, then click through by role/text.
When recording with `codegen`, click through the same way - don't just
copy the URL from the address bar afterward, since that URL will contain
your specific organisation/account IDs and won't be portable to a different
Xero organisation.

## Running the tests

```bash
# Local, no live credentials needed
pytest tests/security -v

# Against the real Xero Demo Company API
pytest tests/api -v

# Full browser journey (slower, needs auth_state.json from step 3)
pytest tests/ui -v
```

## Findings  real Xero behaviour discovered through testing

These weren't known upfront; each was found by writing a test based on a
reasonable assumption, running it against the real Demo Company, and
following up when reality disagreed with the assumption.

| # | Assumption tested | What Xero actually does | Where it lives |
|---|---|---|---|
| 1 | UnitAmount of 0 or negative would be rejected | **Accepted silently**, even calculates tax on a negative amount - flagged as a data-quality gap | `xfail` cases in `test_invoice_amount_partitions` |
| 2 | Total = sum(UnitAmount) | **Tax is auto-added** unless `TaxType: "NONE"` is explicitly set | `test_created_invoice_total_matches_line_items` |
| 3 | Any invoice can be voided | **Only AUTHORISED/SUBMITTED** invoices can be voided; DRAFT must be deleted instead | `create_invoice(status=...)`, `delete_invoice()` |
| 4 | AUTHORISED invoices work the same as DRAFT | **DueDate is required** once a status of AUTHORISED is set, but not for DRAFT | `create_invoice`'s always-sent `Date`/`DueDate` |
| 5 | More than 2 decimal places would be rejected | **Rounded to the nearest cent** (round-half-up), not rejected or truncated | `test_amount_with_excess_decimal_precision_is_rounded_not_rejected` |
| 6 | Contact.Name has some length limit | **Exactly 255 characters** - confirmed both sides of the boundary (255 accepted, 256 rejected) | `ai-007` / `ai-009` in `ai_generated_test_cases.json` |
| 7 | Emoji-only names might be rejected | **Accepted** without any validation error | `ai-006` |
| 8 | UnitAmount sent as a JSON string | **Still open** - UI input masking blocks typing a string, but that says nothing about the API's JSON parsing behaviour | `ai-003`, deliberately left unresolved |
| 9 | A direct URL (e.g. `/Bank/BankRec.aspx`) can jump straight to a specific screen | **Fails or redirects** - Xero embeds per-organisation/per-account IDs in these URLs, so a static link isn't portable across orgs | All page objects rewritten to navigate via UI clicks (dashboard → menu → screen) instead of hardcoded URLs |
| 10 | A "New" button on the dashboard is unambiguous | **Two elements matched**  Playwright's substring matching found both "Create new" (a menu trigger) and "New invoice" (a direct shortcut). The error log itself named both exactly | `invoice_page.py`'s `exact=True` locator, picked from reading the strict-mode violation rather than guessing again |
| 11 | `wait_for_load_state("networkidle")` is a safe generic "page is ready" wait | **Times out on modern SPAs** - Xero keeps background connections open (polling/websockets), so network never goes fully idle even though `load` fires normally | `base_page.py`'s `wait_for_load()` switched to waiting on `"load"` instead |
| 12 | The bank account's Reconcile control is a `link` with fixed text "Reconcile" | **It's a `button`** with a live item count baked into the accessible name (`"Reconcile 20 items"`), confirmed via `codegen --load-storage` | `reconciliation_page.py`'s locator now matches role `button` with a regex pattern instead of an exact string |
| 13 | Short labels like `"To"` are safe to match without `exact=True` | **Substring matching turned a 2-letter label into 8 false-positive matches** - every nav element containing "to" anywhere ("Toggle...", "Accounting tools") - none of which was the real field | `invoice_page.py` now applies `exact=True` preemptively to every short/generic locator, not just the ones that already failed |
| 14 | A test can invent its own reference string and expect a matching bank transaction to exist for it | **Nothing creates that transaction** - real reconciliation matches existing bank statement lines against existing invoices; a randomly generated string has no row to find, by design flaw not locator bug | `test_matching_bank_transaction_reconciles` marked `skip` with the real reason, rather than chasing a selector fix for an unreachable goal |
| 15 | The invoice contact field's label is "To" | **It's "Contact"** - confirmed via a real screenshot of the invoice form, and it's an autocomplete/typeahead, not a plain text box | `invoice_page.py`'s `contact_field` corrected to `get_by_label("Contact")`, with an `Enter` press added to attempt committing a brand-new contact name in the dropdown |

Findings 1-5 came from the hand-written test suite; 6-8 came from resolving
the AI-assisted test cases in `ai_assisted_testing/` (see that folder's
README) through direct manual testing, then converting them from
`pytest.skip()` into real assertions once confirmed.

## Design decisions worth knowing (and being able to explain)

**Real finding: Xero's Invoices API doesn't reject zero or negative amounts.**
`tests/api/test_invoices_api.py`'s boundary tests assumed Xero would reject
a $0 or negative UnitAmount at the API layer -- a reasonable assumption, and
wrong. Running against the real Demo Company showed Xero silently accepts
both, even calculating tax on a negative amount. Rather than quietly
changing the test to expect success (which would hide a real gap), these
cases are marked `xfail` with the discovery documented in the reason string
-- so `pytest -v` output makes the gap visible every run, instead of it
disappearing into a passing test. This is the actual skill Foodstuffs'
listing asks for under "identifying, managing, and clearly communicating
data defects and risks" -- not writing tests that pass, but surfacing where
a system's real behaviour doesn't match a reasonable expectation.

**Why UI tests reuse a saved session instead of scripting the login form.**
Xero enforces MFA, which requires a live code from an authenticator app -
there's no way to script that unattended without either the MFA secret
itself (see the `pyotp` alternative documented in `save_auth_state.py`) or
accepting that a human logs in occasionally. Rather than pretending this
away, `save_auth_state.py` makes it explicit: a human authenticates once,
Playwright's `storage_state` mechanism persists that session, and every
test after that loads the session instead of re-logging in. This is a real
pattern used in production test suites against any MFA-protected system,
not a workaround unique to a learning project.

**Why the security suite runs locally, not against Xero's live UI.**
Firing SQL injection payloads at Xero's real form fields would only prove
Xero's backend is well-built - it wouldn't prove I understand *why* an
injection succeeds or *why* a specific defence stops it. `security_demo/app.py`
runs the exact same OWASP-derived payload set against a naive
(string-concatenation) endpoint and a parameterized-query endpoint, side by
side, so the vulnerability and its fix are both directly observable.

**Why UI tests run nightly, not on every push.**
A full browser login is slower and more failure-prone than an API call, and
Xero enforces API/usage limits. Gating the UI journey to a scheduled run
(see `.github/workflows/tests.yml`) is a deliberate CI design choice, not a
missing feature.

**Why test data is UUID-suffixed and cleaned up via fixtures, not a reset endpoint.**
Testing against a real, shared, stateful system means there's no way to wipe
it between test runs. Isolation instead comes from two things: every test
creates uniquely-named records (`unique_contact_name`, `unique_invoice_reference`
fixtures) so it can never collide with data from a previous run, and
`cleanup_contacts` / `cleanup_invoices` fixtures archive or void whatever
was created, in teardown, regardless of whether the test passed or failed.

**Why authentication uses a Custom Connection instead of the standard browser OAuth flow.**
The standard Authorization Code flow needs a browser login, produces a
refresh token that's single-use and must be persisted and rotated, and
requires a `GET /connections` call to discover which organisation you're
even talking to. A Custom Connection is scoped to one organisation from the
moment it's created in the Developer Portal, so `utils/xero_auth.py` just
exchanges a client ID/secret directly for an access token whenever needed 
no browser step, no refresh token to lose, no tenant lookup.
