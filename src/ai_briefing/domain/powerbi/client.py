import os
from collections.abc import Callable

import requests

from .auth import get_access_token


def _clean_row(row: dict[str, object]) -> dict[str, object]:
    """Normalize the API's messy column keys ("Table[Col" / "[Col]") to plain names."""
    clean: dict[str, object] = {}
    for key, value in row.items():
        name = key.rsplit("[", 1)[-1].rstrip("]").strip()
        clean[name] = value
    return clean


class PowerBIClient:
    """Power BI REST operations.

    Authentication is injected as a zero-arg callable that returns an access
    token. Pass `get_access_token` (the function, not its result) so every
    request re-checks MSAL's cache and auto-refreshes the token near expiry —
    important for a long-running server.
    """

    def __init__(self, token_provider: Callable[[], str]):
        self._token_provider: Callable[[], str] = token_provider

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token_provider()}"}

    def list_datasets(self, workspace_id: str) -> list[dict[str, object]]:
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
        res = requests.get(url, headers=self._headers(), timeout=30)
        res.raise_for_status()
        return res.json()["value"]

    def run_dax(self, dataset_id: str, query: str) -> list[dict[str, object]]:
        """Run one DAX query and return its rows (the API allows one per call)."""
        url = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries"
        payload = {"queries": [{"query": query}]}
        res = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        if not res.ok:
            raise RuntimeError(f"DAX query failed ({res.status_code}): {res.text}")
        rows = res.json()["results"][0]["tables"][0]["rows"]
        return [_clean_row(row) for row in rows]

    def list_tables(self, dataset_id: str) -> list[dict[str, object]]:
        return self.run_dax(dataset_id, "EVALUATE INFO.TABLES()")

    def list_columns(self, dataset_id: str) -> list[dict[str, object]]:
        return self.run_dax(dataset_id, "EVALUATE INFO.COLUMNS()")


if __name__ == "__main__":
    dataset_id = os.getenv("DATASET_ID", "")
    if not dataset_id:
        raise SystemExit("Missing required env var: DATASET_ID")

    client = PowerBIClient(get_access_token)

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
