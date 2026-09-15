"""
Xero OAuth2 token handling -- Custom Connection (client_credentials grant).

This is deliberately simpler than the standard Authorization Code flow:
a Custom Connection is scoped to exactly one organisation from the moment
it's created in the Xero Developer Portal, so there's no browser login step,
no refresh token to persist and rotate, and no GET /connections call needed
to discover a tenant ID. Just a client_id and client_secret, exchanged
directly for an access token whenever the current one is missing or expired.

Setup (one-time, manual, in the Xero Developer Portal):
1. developer.xero.com/app/manage -> New App -> select "Custom connection".
2. Select the scopes you need (accounting.transactions, accounting.contacts,
   accounting.settings) and authorise against your Demo Company as the
   authorising user.
3. Configuration tab -> Generate a secret. Copy the Client ID and Client
   Secret into your .env file (see .env.example) -- that's the whole setup.

Note: Custom Connections are a Xero "premium" feature for a real customer
organisation, but Xero explicitly allows connecting one to the Demo Company
for free for development purposes.
"""
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://identity.xero.com/connect/token"


class XeroAuthError(Exception):
    pass


class XeroTokenManager:
    def __init__(self):
        self.client_id = os.getenv("XERO_CLIENT_ID")
        self.client_secret = os.getenv("XERO_CLIENT_SECRET")

        if not all([self.client_id, self.client_secret]):
            raise XeroAuthError(
                "Missing XERO_CLIENT_ID / XERO_CLIENT_SECRET. Create a Custom "
                "Connection app in the Xero Developer Portal and populate .env "
                "(see .env.example)."
            )

        self.access_token = None
        self.expires_at = 0

    def _fetch_token(self):
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if response.status_code != 200:
            raise XeroAuthError(f"Token request failed: {response.status_code} {response.text}")

        body = response.json()
        self.access_token = body["access_token"]
        self.expires_at = time.time() + body["expires_in"] - 60  # 60s safety margin

    def get_headers(self):
        if self.access_token is None or time.time() >= self.expires_at:
            self._fetch_token()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
