import json
import os
from collections.abc import Iterator
from typing import cast

import requests
from dotenv import load_dotenv

_ = load_dotenv()


class BitrixError(RuntimeError):
    """Raised when the Bitrix24 API returns an error in the response body."""


def _flatten_params(prefix: str, value: object) -> list[tuple[str, str]]:
    """Flatten nested dicts/lists into Bitrix24's PHP-style query notation.

    {"filter": {"stageId": "X"}}  ->  [("filter[stageId]", "X")]
    {"select": ["id", "title"]}   ->  [("select[]", "id"), ("select[]", "title")]
    """
    flat: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, sub in value.items():
            flat.extend(_flatten_params(f"{prefix}[{key}]", sub))
    elif isinstance(value, (list, tuple)):
        for sub in value:
            flat.extend(_flatten_params(f"{prefix}[]", sub))
    elif isinstance(value, bool):
        flat.append((prefix, "Y" if value else "N"))
    elif value is not None:
        flat.append((prefix, str(value)))
    return flat


class BitrixClient:
    """Generic client for the Bitrix24 incoming-webhook REST API.

    Usage:
        client = BitrixClient("https://portal.example.com/rest/17301/token/")
        items = client.item_list(168, filter={"stageId": "TS_ISSUED"})
    """

    def __init__(self, base_url: str):
        self._base_url: str = base_url.rstrip("/")

    # -- low-level ---------------------------------------------------------
    def call(
        self,
        method: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Call any Bitrix24 REST method and return its `result` object.

        Bitrix24 returns HTTP 200 even on errors, with `error`/`error_description`
        in the body — so we inspect the body, not just the status code.
        """
        flat: list[tuple[str, str]] = []
        for key, value in (params or {}).items():
            flat.extend(_flatten_params(key, value))

        res = requests.get(f"{self._base_url}/{method}.json", params=flat)
        res.raise_for_status()
        data = cast(dict[str, object], res.json())

        if "error" in data:
            raise BitrixError(f"{data.get('error')}: {data.get('error_description')}")

        return cast(dict[str, object], data.get("result"))

    # -- CRM item helpers --------------------------------------------------
    def item_get(self, entity_type_id: int, item_id: int) -> dict[str, object]:
        result = self.call(
            "crm.item.get",
            {"entityTypeId": entity_type_id, "id": item_id},
        )
        return cast(dict[str, object], result.get("item"))

    def item_list(
        self,
        entity_type_id: int,
        filter: dict[str, object] | None = None,
        select: list[str] | None = None,
        order: dict[str, str] | None = None,
        start: int = 0,
    ) -> dict[str, object]:
        """Return one page: {"items": [...], "next": int | None, "total": int}."""
        params: dict[str, object] = {"entityTypeId": entity_type_id, "start": start}
        if filter:
            params["filter"] = filter
        if select:
            params["select"] = select
        if order:
            params["order"] = order
        return self.call("crm.item.list", params)

    def item_fields(self, entity_type_id: int) -> dict[str, object]:
        result = self.call("crm.item.fields", {"entityTypeId": entity_type_id})
        return cast(dict[str, object], result.get("fields"))

    def item_add(
        self,
        entity_type_id: int,
        fields: dict[str, object],
    ) -> dict[str, object]:
        return self.call(
            "crm.item.add",
            {"entityTypeId": entity_type_id, "fields": fields},
        )

    def item_update(
        self,
        entity_type_id: int,
        item_id: int,
        fields: dict[str, object],
    ) -> dict[str, object]:
        return self.call(
            "crm.item.update",
            {"entityTypeId": entity_type_id, "id": item_id, "fields": fields},
        )

    def item_delete(self, entity_type_id: int, item_id: int) -> dict[str, object]:
        return self.call(
            "crm.item.delete",
            {"entityTypeId": entity_type_id, "id": item_id},
        )

    # -- helpers -----------------------------------------------------------
    def iter_items(
        self,
        entity_type_id: int,
        filter: dict[str, object] | None = None,
        select: list[str] | None = None,
        order: dict[str, str] | None = None,
        max_items: int | None = None,
    ) -> Iterator[dict[str, object]]:
        """Lazily yield items across all pages, stopping after `max_items`."""
        start = 0
        yielded = 0
        while True:
            page = self.item_list(entity_type_id, filter, select, order, start)
            items = cast(list[dict[str, object]], page.get("items", []))
            for item in items:
                yield item
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            if not items or not page.get("next"):
                return
            start = cast(int, page.get("next"))

    def get_enum_map(self, entity_type_id: int) -> dict[str, dict[str, str]]:
        """Build {fieldName: {enumId: enumLabel}} from crm.item.fields."""
        fields = self.item_fields(entity_type_id)
        enum_map: dict[str, dict[str, str]] = {}
        for field_name, meta in fields.items():
            if not isinstance(meta, dict):
                continue
            items = meta.get("items")
            if not isinstance(items, list):
                continue
            mapping: dict[str, str] = {}
            for entry in items:
                if isinstance(entry, dict):
                    id_ = entry.get("ID")
                    label = entry.get("VALUE")
                    if id_ is not None and label is not None:
                        mapping[str(id_)] = str(label)
            if mapping:
                enum_map[field_name] = mapping
        return enum_map

    def decode_item(
        self,
        item: dict[str, object],
        enum_map: dict[str, dict[str, str]],
    ) -> dict[str, object]:
        """Return a copy of `item` with enum-ID fields translated to their labels."""
        decoded = dict(item)
        for field, mapping in enum_map.items():
            value = decoded.get(field)
            if isinstance(value, (str, int)) and str(value) in mapping:
                decoded[field] = mapping[str(value)]
        return decoded


if __name__ == "__main__":
    webhook = os.getenv("BITRIX_WEBHOOK", "")
    if not webhook:
        raise SystemExit("Missing required env var: BITRIX_WEBHOOK")

    client = BitrixClient(webhook)
    entity_type_id = 168

    enum_map = client.get_enum_map(entity_type_id)
    print(f"Decodable enum fields: {len(enum_map)}\n")

    for item in client.iter_items(
        entity_type_id,
        select=["id", "title", "stageId", "ufCrm31Taxation", "ufCrm31WhatDoesHeWantLease"],
        max_items=5,
    ):
        print(json.dumps(client.decode_item(item, enum_map), ensure_ascii=False, indent=2))
