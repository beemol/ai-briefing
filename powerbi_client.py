import os

import requests

from powerbi_auth import get_access_token


class PowerBIClient:
    """Power BI REST operations. Authentication is injected as an access token."""

    def __init__(self, access_token: str):
        self._headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}

    def list_datasets(self, workspace_id: str) -> list[dict[str, object]]:
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
        res = requests.get(url, headers=self._headers)
        res.raise_for_status()
        return res.json()["value"]

    def run_dax(self, dataset_id: str, query: str) -> list[dict[str, object]]:
        """Run one DAX query and return its rows (the API allows one per call)."""
        url = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"
        payload = {"queries": [{"query": query}]}
        res = requests.post(url, headers=self._headers, json=payload)
        if not res.ok:
            raise RuntimeError(f"DAX query failed ({res.status_code}): {res.text}")
        return res.json()["results"][0]["tables"][0]["rows"]

    def list_tables(self, dataset_id: str) -> list[dict[str, object]]:
        return self.run_dax(dataset_id, "EVALUATE INFO.TABLES()")

    def list_columns(self, dataset_id: str) -> list[dict[str, object]]:
        return self.run_dax(dataset_id, "EVALUATE INFO.COLUMNS()")


if __name__ == "__main__":
    dataset_id = os.getenv("DATASET_ID", "")
    if not dataset_id:
        raise SystemExit("Missing required env var: DATASET_ID")

    client = PowerBIClient(get_access_token())

    tables = client.list_tables(dataset_id)
    columns = client.list_columns(dataset_id)

    table_names = {row.get("ID"): row.get("Name") for row in tables}

    print("==============================================")
    print("              TABLES                          ")
    print("==============================================")
    for table in tables:
        print(f"📊 {table.get('Name')}")

    print("\n==============================================")
    print("              COLUMNS                         ")
    print("==============================================")
    for col in columns:
        table_name = table_names.get(col.get("TableID"), "?")
        print(f"   · {table_name}.{col.get('Name')}  ({col.get('DataType')})")
