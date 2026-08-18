import os

import requests
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
WORKSPACE_ID = os.getenv("WORKSPACE_ID")

# 1. Fetch token directly using Client Credentials (MFA is bypassed)
token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
token_data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "https://analysis.windows.net/powerbi/api/.default"
}

# The Client Credentials flow naturally expects urlencoded form format
token_res = requests.post(token_url, data=token_data).json()
access_token = token_res["access_token"]
headers = {"Authorization": f"Bearer {access_token}"}

# 2. Extract database entities
datasets_url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets"
datasets = requests.get(datasets_url, headers=headers).json()

print("==============================================")
print("   AVAILABLE POWER BI DATABASES (DATASETS)   ")
print("==============================================")

datasets_list = datasets.get('value', [])
if not datasets_list:
    print("No active databases found or account lacks workspace access permissions.")

for ds in datasets_list:
    print(f"🔹 Database Name : {ds.get('name')}")
    print(f"   Database ID   : {ds.get('id')}")
    print(f"   Configured By : {ds.get('configuredBy')}")
    print(f"   Is Refreshable: {ds.get('isRefreshable')}")
    print("-" * 46)
