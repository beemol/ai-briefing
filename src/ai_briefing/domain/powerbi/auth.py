import os
from typing import cast

import msal
from dotenv import load_dotenv

_ = load_dotenv()


def get_token_for(scope: str) -> str:
    """Authenticate as a service principal and return an access token for `scope`.

    No user, no MFA, no browser — this authenticates the app itself.
    """
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    missing = [k for k, v in {
        "TENANT_ID": tenant_id,
        "CLIENT_ID": client_id,
        "CLIENT_SECRET": client_secret,
    }.items() if not v]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

    authority = f"https://login.microsoftonline.com/{tenant_id}"

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )

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
