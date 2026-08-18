import os
from typing import cast

import msal
import requests
from dotenv import load_dotenv

_ = load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
WORKSPACE_ID = os.getenv("WORKSPACE_ID")

missing = [k for k, v in {
    "TENANT_ID": TENANT_ID,
    "CLIENT_ID": CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET
}.items() if not v]
if missing:
    raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

SCOPE = "https://analysis.windows.net/powerbi/api/.default"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

app = msal.ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=AUTHORITY,
)

# Client credentials = app identity. No user, no MFA, no browser.
result = cast(dict[str, str | int] | None, app.acquire_token_for_client(scopes=[SCOPE]))

if not result:
    raise SystemExit("Token request returned no result.")

if "access_token" not in result:
    raise SystemExit(
        f"Token failed: {result.get('error')} — {result.get('error_description')}"
    )

access_token = result["access_token"]
headers = {"Authorization": f"Bearer {access_token}"}

workspaces_url = "https://api.powerbi.com/v1.0/myorg/groups"
workspaces_res = requests.get(workspaces_url, headers=headers)

if workspaces_res.status_code != 200:
    print(f"Error calling workspaces API: {workspaces_res.status_code}")
    print(f"Response body: {workspaces_res.text}")
    raise SystemExit("Failed to get workspaces.")

print("Workspaces found:")
print(workspaces_res.json())

datasets_url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets"
datasets_res = requests.get(datasets_url, headers=headers)
datasets_res.raise_for_status()
datasets = datasets_res.json()

print("==============================================")
print("          DATASETS IN WORKSPACE               ")
print("==============================================")

datasets_list = datasets.get("value", [])
if not datasets_list:
    print("No datasets found in this workspace.")

for ds in datasets_list:
    print(f"🔹 Name        : {ds.get('name')}")
    print(f"   Dataset ID  : {ds.get('id')}")
    print(f"   Configured  : {ds.get('configuredBy')}")
    print(f"   Refreshable : {ds.get('isRefreshable')}")
    print("-" * 46)
