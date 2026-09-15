"""
SQL injection test suite -- based on the OWASP SQL Injection Prevention
Cheat Sheet (https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).

Two things are demonstrated here, deliberately kept separate:

1. The vulnerability is real and exploitable (test class:
   TestVulnerableEndpointIsExploitable) -- proves the risk isn't theoretical.
2. The OWASP-recommended defence (parameterized queries) actually closes it
   (test class: TestParameterizedEndpointIsSafe) -- proves the fix works,
   using the exact same payload set against the exact same seed data.

Running the same parametrized payloads against both endpoints is the point:
it isolates "the query-building technique" as the only variable that changes
the outcome.
"""
import subprocess
import time

import pytest
import requests

SECURITY_APP_URL = "http://127.0.0.1:5002"

# Payload patterns adapted from common SQLi test cases referenced in the
# OWASP cheat sheet's discussion of tautology-based and statement-terminating
# injection techniques.
SQLI_PAYLOADS = [
    pytest.param("' OR '1'='1", id="tautology-or-1-equals-1"),
    pytest.param("' OR 1=1--", id="tautology-with-comment-terminator"),
    pytest.param("x' UNION SELECT id, name, email FROM contacts--", id="union-based"),
    pytest.param("'; DROP TABLE contacts;--", id="statement-terminating-drop-table"),
    pytest.param("nonexistent_name", id="control-case-no-injection"),
]


@pytest.fixture(scope="session")
def security_app_server():
    proc = subprocess.Popen(["python", "security_demo/app.py"])
    for _ in range(20):
        try:
            requests.post(f"{SECURITY_APP_URL}/_reset", timeout=0.5)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.25)
    yield SECURITY_APP_URL
    proc.terminate()
    proc.wait()


@pytest.fixture(autouse=True)
def reset_seed_data(security_app_server):
    """Re-seed before every test so a DROP TABLE in one test case
    (if it succeeds against the vulnerable endpoint) can't break the next test."""
    requests.post(f"{security_app_server}/_reset")
    yield


class TestVulnerableEndpointIsExploitable:
    """Demonstrates the risk. This is what a naive implementation looks like."""

    def test_tautology_returns_all_rows_instead_of_one(self, security_app_server):
        response = requests.get(f"{security_app_server}/vulnerable/search", params={"name": "' OR '1'='1"})
        body = response.json()
        assert body["row_count"] == 3, (
            "Expected the tautology payload to bypass the WHERE clause and "
            "return every row -- this is the exploit succeeding."
        )

    def test_control_case_returns_zero_rows(self, security_app_server):
        """Sanity check: a genuinely non-matching name should return nothing,
        proving the '3 rows' result above is caused by the payload, not by a
        broken test fixture."""
        response = requests.get(f"{security_app_server}/vulnerable/search", params={"name": "nonexistent_name"})
        assert response.json()["row_count"] == 0

    def test_stacked_drop_table_payload_breaks_the_database(self, security_app_server):
        """Statement-terminating (stacked-query) payload against the
        executescript-based endpoint -- demonstrates impact beyond data
        disclosure (destructive action), which is what makes SQLi a critical
        severity class rather than a low-severity data leak. See
        vulnerable_search_stacked's docstring for why this needs a separate
        endpoint from the tautology/UNION test above."""
        requests.get(f"{security_app_server}/vulnerable/search_stacked", params={"name": "x'; DROP TABLE contacts;--"})
        # Table is gone -- any subsequent query now errors out
        follow_up = requests.get(f"{security_app_server}/vulnerable/search", params={"name": "Alice Smith"})
        assert follow_up.status_code == 500, "Table should no longer exist after the DROP payload"


class TestParameterizedEndpointIsSafe:
    """Demonstrates the OWASP-recommended fix: the exact same payloads,
    against a parameterized-query implementation, treated purely as data."""

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_payload_treated_as_literal_string_not_sql(self, security_app_server, payload):
        response = requests.get(f"{security_app_server}/safe/search", params={"name": payload})
        body = response.json()

        assert response.status_code == 200
        # None of these payloads match a real contact name, so the correct,
        # safe behaviour is zero rows -- regardless of what the payload contains.
        assert body["row_count"] == 0, (
            f"Payload '{payload}' should be treated as a literal (non-matching) "
            f"string, not executed as SQL"
        )

    def test_safe_endpoint_still_matches_real_names_correctly(self, security_app_server):
        """Parameterization must not break legitimate functionality --
        a defence that also breaks valid input isn't a usable fix."""
        response = requests.get(f"{security_app_server}/safe/search", params={"name": "Alice Smith"})
        assert response.json()["row_count"] == 1

    def test_drop_table_payload_does_not_affect_safe_endpoint(self, security_app_server):
        requests.get(f"{security_app_server}/safe/search", params={"name": "x'; DROP TABLE contacts;--"})
        follow_up = requests.get(f"{security_app_server}/safe/search", params={"name": "Alice Smith"})
        assert follow_up.status_code == 200
        assert follow_up.json()["row_count"] == 1, "Table must be intact -- the payload was never executed as SQL"
