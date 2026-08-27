import os
from typing import cast

import msal
from dotenv import load_dotenv

_ = load_dotenv()

# Memoized MSAL app. Keeping a single instance (instead of building a new one
# on every call) lets MSAL's in-memory token cache persist across requests:
# acquire_token_for_client() then returns a cached token and auto-refreshes it
# near expiry, so a long-running server doesn't re-authenticate to Azure AD
# every time it needs a token.
_msal_app: msal.ConfidentialClientApplication | None = None


def _get_msal_app() -> msal.ConfidentialClientApplication:
    """Return the shared MSAL app, building it from env vars on first use."""
    global _msal_app
    if _msal_app is not None:
        return _msal_app

    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    missing = [
        k
        for k, v in {
            "TENANT_ID": tenant_id,
            "CLIENT_ID": client_id,
            "CLIENT_SECRET": client_secret,
        }.items()
        if not v
    ]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

    _msal_app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
    return _msal_app


def get_token_for(scope: str) -> str:
    """Authenticate as a service principal and return an access token for `scope`.

    No user, no MFA, no browser — this authenticates the app itself. Tokens are
    cached by MSAL and refreshed automatically near expiry.
    """
    app = _get_msal_app()

    result = cast(
        dict[str, str | int] | None,
        app.acquire_token_for_client(scopes=[scope]),
    )

    if not result:
        raise SystemExit("Token request returned no result.")

    if "access_token" not in result:
        raise SystemExit(
            f"Token failed: {result.get('error')} — {result.get('error_description')}"
        )

    return cast(str, result["access_token"])


def get_access_token() -> str:
    """Power BI API access token (default scope)."""
    return get_token_for("https://analysis.windows.net/powerbi/api/.default")
