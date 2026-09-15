"""
Vulnerable-vs-safe SQL injection demo.

Why this exists (say this in interview):
Firing OWASP SQLi payloads at a real Xero form only proves Xero's backend is
well-built -- it doesn't prove I understand *why* an injection attack works
or *why* a specific defence stops it. This local app puts a naive
(string-concatenation) endpoint next to a parameterized-query endpoint so the
same payload set can be run against both, showing the vulnerability and its
fix side by side.

OWASP's primary recommendation (SQL Injection Prevention Cheat Sheet) is:
parameterized queries / prepared statements. The reason it works: the query
structure and the user-supplied value are sent to the database as two
separate channels. The database always treats the parameter as *data*, so it
is structurally impossible for it to be reinterpreted as SQL syntax --
regardless of what characters it contains. String concatenation collapses
those two channels into one string before the database ever sees it, so a
quote or comment character in the input can change the query's meaning.
"""
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
DB_PATH = ":memory:"

# A single shared in-memory connection so both endpoints see the same seed data
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)


def _seed():
    cur = _conn.cursor()
    cur.execute("DROP TABLE IF EXISTS contacts")
    cur.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    cur.executemany(
        "INSERT INTO contacts (name, email) VALUES (?, ?)",
        [
            ("Alice Smith", "alice@example.com"),
            ("Bob Jones", "bob@example.com"),
            ("Carol Lee", "carol@example.com"),
        ],
    )
    _conn.commit()


_seed()


@app.route("/vulnerable/search")
def vulnerable_search():
    """
    INTENTIONALLY VULNERABLE to tautology- and UNION-based injection.
    Builds the query with string concatenation. Do not copy this pattern
    into real code -- it exists to demonstrate the risk.
    """
    name = request.args.get("name", "")
    query = f"SELECT id, name, email FROM contacts WHERE name = '{name}'"
    cur = _conn.cursor()
    try:
        cur.execute(query)
        rows = cur.fetchall()
        return jsonify({"row_count": len(rows), "rows": rows, "executed_query": query})
    except sqlite3.Error as e:
        # A real vulnerable app leaking a raw DB error is itself a finding
        return jsonify({"row_count": 0, "rows": [], "db_error": str(e)}), 500


@app.route("/vulnerable/search_stacked")
def vulnerable_search_stacked():
    """
    A SEPARATE endpoint to demonstrate STACKED-QUERY injection specifically
    (e.g. "'; DROP TABLE contacts;--").

    Why this needs its own endpoint: Python's sqlite3 Cursor.execute() only
    ever runs the FIRST statement in a string, even when a second one is
    concatenated after a semicolon -- so a naive test expecting a stacked
    payload to succeed against plain execute() would fail, not because the
    input is safe, but because of a driver-level limitation specific to this
    database library. executescript() lifts that restriction, which is what
    makes the destructive/stacked-query technique observable here. This is
    a genuinely useful thing to know: exploitability of stacked queries
    depends on the driver/database combination (e.g. some MySQL client
    libraries allow multi-statement execution by default; most modern
    PostgreSQL/MySQL drivers used with parameterized APIs do not) -- so an
    interviewer asking "does this attack always work?" has a real answer:
    "it depends on whether the driver permits multiple statements per call,
    not just on whether the query is concatenated."
    """
    name = request.args.get("name", "")
    query = f"SELECT id, name, email FROM contacts WHERE name = '{name}';"
    cur = _conn.cursor()
    try:
        cur.executescript(query)
        return jsonify({"executed_query": query, "note": "executescript does not return SELECT rows"})
    except sqlite3.Error as e:
        return jsonify({"db_error": str(e)}), 500


@app.route("/safe/search")
def safe_search():
    """
    SAFE. Uses a parameterized query (OWASP's primary defence).
    The '?' placeholder and the tuple below are sent to sqlite3 separately --
    the value can never be interpreted as part of the SQL statement.
    """
    name = request.args.get("name", "")
    query = "SELECT id, name, email FROM contacts WHERE name = ?"
    cur = _conn.cursor()
    cur.execute(query, (name,))
    rows = cur.fetchall()
    return jsonify({"row_count": len(rows), "rows": rows, "executed_query": query})


@app.route("/_reset", methods=["POST"])
def reset():
    _seed()
    return jsonify({"status": "reseeded"})


if __name__ == "__main__":
    app.run(port=5002)
