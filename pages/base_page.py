"""
Base Page Object.

Concept demonstrated: Page Object Model. Page objects expose only actions
(do_x) and state queries (get_x / is_x_visible) -- they never contain
assertions. Assertions belong in test files. This split is what lets the
same page object be reused for both positive and negative test cases: a
"get_validation_error_text()" method doesn't presuppose whether an error
should or shouldn't be present -- the test decides what to assert.
"""


class BasePage:
    def __init__(self, page):
        self.page = page

    def goto(self, url):
        self.page.goto(url)

    def wait_for_load(self):
        """
        Deliberately waits for "load", not "networkidle". A real test run
        against Xero's Reports screen timed out here at 30s with "load"
        already fired successfully -- Xero's UI is a modern single-page app
        that keeps background connections open (polling, websockets,
        analytics beacons), so the network never goes fully idle and
        "networkidle" waits for a condition that may simply never occur.
        This is a known, common Playwright pitfall on modern SPAs generally,
        not specific to Xero.

        "load" firing doesn't guarantee every dynamic element has rendered,
        though -- for anything timing-sensitive, prefer waiting on a
        specific locator to become visible (e.g.
        page.wait_for_selector(...) or locator.wait_for()) rather than this
        generic page-level wait.
        """
        self.page.wait_for_load_state("load")
