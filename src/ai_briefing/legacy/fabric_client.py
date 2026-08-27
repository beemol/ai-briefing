import json
import os
from typing import cast

import requests

from ai_briefing.domain.powerbi.auth import get_token_for

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


class FabricClient:
    """Minimal client for the Microsoft Fabric REST API (semantic models)."""

    def __init__(self, access_token: str):
        self._headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}

    def get_workspace(self, workspace_id: str) -> dict[str, object]:
        url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
        res = requests.get(url, headers=self._headers)
        res.raise_for_status()
        return cast(dict[str, object], res.json())

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

    def get_tmdl(self, item_id: str) -> str:
        """Return the semantic model definition as TMDL (tables/columns/measures)."""
        url = f"https://api.fabric.microsoft.com/v1/items/{item_id}/getTMDL"
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

    print("=== WORKSPACE DETAILS (capacity type matters) ===")
    try:
        print(json.dumps(client.get_workspace(workspace_id), indent=2, ensure_ascii=False))
    except requests.HTTPError as exc:
        resp = exc.response
        # NB: `if resp` is wrong here — requests.Response.__bool__ means
        # "status < 400", so a 404 response is falsy. Check for None instead.
        status = resp.status_code if resp is not None else "?"
        body = resp.text if resp is not None else str(exc)
        print("workspace GET failed:", status, body)

    print("\n=== ALL ITEMS (real types, no filter) ===")
    items = client.list_items(workspace_id)
    for item in items:
        print(f"  [{item.get('type')}] {item.get('displayName')}  ->  {item.get('id')}")

    target = os.getenv("DATASET_NAME", "Воронка Лизинг_5.0")
    item_id = next(
        (
            str(item.get("id"))
            for item in items
            if str(item.get("type")) == "SemanticModel"
            and str(item.get("displayName")) == target
        ),
        None,
    )
    if not item_id:
        raise SystemExit(f"Item '{target}' not found in workspace.")

    print(f"\n=== ITEM DETAILS ({item_id}) ===")
    try:
        print(json.dumps(client.get_item(item_id), indent=2, ensure_ascii=False))
    except requests.HTTPError as exc:
        resp = exc.response
        status = resp.status_code if resp is not None else "?"
        body = resp.text if resp is not None else str(exc)
        print("get_item failed:", status, body)

    print(f"\n=== TMDL for '{target}' ===")
    try:
        tmdl = client.get_tmdl(item_id)
        print(tmdl[:20000])
    except requests.HTTPError as exc:
        resp = exc.response
        status = resp.status_code if resp is not None else "?"
        body = resp.text if resp is not None else str(exc)
        print("getTMDL failed:", status, body)
        raise SystemExit(1)
