import json
import os
from typing import cast

import requests

from powerbi_auth import get_token_for

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


class FabricClient:
    """Minimal client for the Microsoft Fabric REST API (semantic models)."""

    def __init__(self, access_token: str):
        self._headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}

    def list_items(
        self,
        workspace_id: str,
        item_type: str | None = None,
    ) -> list[dict[str, object]]:
        url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items"
        params: dict[str, str] = {}
        if item_type:
            params["type"] = item_type
        res = requests.get(url, headers=self._headers, params=params)
        res.raise_for_status()
        return cast(list[dict[str, object]], res.json().get("value", []))

    def get_item(self, item_id: str) -> dict[str, object]:
        url = f"https://api.fabric.microsoft.com/v1/items/{item_id}"
        res = requests.get(url, headers=self._headers)
        res.raise_for_status()
        return cast(dict[str, object], res.json())

    def get_tmdl(self, item_id: str, workspace_id: str | None = None) -> str:
        """Return the semantic model definition as TMDL (tables/columns/measures)."""
        url = f"https://api.fabric.microsoft.com/v1/items/{item_id}/getTMDL"
        res = requests.get(url, headers=self._headers)
        if res.status_code == 404 and workspace_id:
            # Fallback: workspace-scoped semantic-model endpoint.
            url = (
                f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
                f"/semanticModels/{item_id}/getTMDL"
            )
            res = requests.get(url, headers=self._headers)
        res.raise_for_status()
        try:
            data = res.json()
        except ValueError:
            return res.text  # plain-text TMDL body
        if isinstance(data, dict) and isinstance(data.get("value"), str):
            return data["value"]
        return res.text


if __name__ == "__main__":
    workspace_id = os.getenv("WORKSPACE_ID", "")
    if not workspace_id:
        raise SystemExit("Missing required env var: WORKSPACE_ID")

    client = FabricClient(get_token_for(FABRIC_SCOPE))

    items = client.list_items(workspace_id, item_type="SemanticModel")
    print("=== SEMANTIC MODELS IN WORKSPACE ===")
    for item in items:
        print(f"  [{item.get('type')}] {item.get('displayName')}  ->  {item.get('id')}")

    target = os.getenv("DATASET_NAME", "Воронка Лизинг_5.0")
    item_id = next(
        (str(item.get("id")) for item in items if str(item.get("displayName")) == target),
        None,
    )
    if not item_id:
        raise SystemExit(f"Semantic model '{target}' not found in workspace.")

    print(f"\n=== ITEM DETAILS ({item_id}) ===")
    try:
        print(json.dumps(client.get_item(item_id), indent=2, ensure_ascii=False))
    except requests.HTTPError as exc:
        resp = exc.response
        if resp is not None:
            print(resp.status_code, resp.text)

    print(f"\n=== TMDL for '{target}' ===")
    try:
        tmdl = client.get_tmdl(item_id, workspace_id)
        print(tmdl[:20000])
    except requests.HTTPError as exc:
        resp = exc.response
        if resp is not None:
            print("getTMDL failed:", resp.status_code)
            print(resp.text)
        raise SystemExit(1)
