# Postman collection

`Xero_Demo_Company_API_Tests.postman_collection.json` covers the same
endpoints and validation logic as `tests/api/test_invoices_api.py`
(invoice creation boundary cases, contact completeness/uniqueness rules,
cleanup via void/archive). It exists alongside the pytest suite on purpose,
not as a replacement for it — the two tools serve different moments in the
testing workflow:

| | Pytest suite | Postman collection |
|---|---|---|
| Runs in CI on every push | Yes | No |
| Best for | Regression, repeatable automated checks | Manual/exploratory testing, quick sanity checks, sharing a request with a non-technical teammate |
| How assertions are written | Python `assert` statements | `pm.test()` scripts, same assertions expressed in JS |

In practice: when investigating a new Xero endpoint or a bug report, it's
faster to explore it interactively in Postman first, confirm the expected
behaviour, then port the verified case into the pytest suite for
permanent automated coverage. This collection is that first step, kept
in the repo as a record of it.

## How to use

1. Open Postman → Import → select both `.postman_collection.json` and
   `.postman_environment.json` from this folder.
2. Get an access token via the Custom Connection client_credentials flow
   (see the root README's OAuth setup section) — either run a quick curl/Python
   snippet against `https://identity.xero.com/connect/token`, or use Postman
   itself: create a new request, POST to that URL with Body → x-www-form-urlencoded
   containing `grant_type=client_credentials`, `client_id`, `client_secret`,
   send it, and copy the `access_token` from the response.
3. Paste that token into the environment's `access_token` value. No tenant ID
   is needed — Custom Connections are already scoped to one organisation.
4. Run individual requests, or use Postman's Collection Runner to execute
   the whole folder in sequence (Invoices, then Contacts) and see the
   `pm.test()` results.
