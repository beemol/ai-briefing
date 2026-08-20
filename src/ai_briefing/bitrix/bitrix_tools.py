from typing import Any, cast, override

from ai_briefing.agent.toolkit import Toolkit, serialize_tool_result

from .bitrix_client import BitrixClient

# The "Лизинг" smart process (dynamic CRM entity).
ENTITY_TYPE_ID = 168

# Fields returned by default. PII (name/phone) excluded before going live.
SELECT_KEYS = [
    "id",
    "title",
    "stageId",
    "ufCrm31Inn",
    "ufCrm31ConclusionHeadSc",
    "createdTime",
    "updatedTime",
]

class BitrixTools(Toolkit):
    """High-level, prompt-friendly operations over the leasing smart process."""

    def __init__(self, client: BitrixClient):
        self._client: BitrixClient = client
        self._enum_map: dict[str, dict[str, str]] = client.get_enum_map(ENTITY_TYPE_ID)

    def _decode(self, item: dict[str, object]) -> dict[str, object]:
        return self._client.decode_item(item, self._enum_map)

    @override
    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "leads_by_stage",
                "description": (
                    "List leasing leads currently in a given pipeline stage. "
                    "Example stage ids: TS_ISSUED, SECURITY_COUNCIL_REFUSAL, "
                    "APPLICATION_DIRECT_ADVANCE, FAIL."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "stage_id": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["stage_id"],
                },
            },
            {
                "name": "count_in_stage",
                "description": "Count how many leasing leads are in a given pipeline stage.",
                "input_schema": {
                    "type": "object",
                    "properties": {"stage_id": {"type": "string"}},
                    "required": ["stage_id"],
                },
            },
            {
                "name": "search_by_inn",
                "description": "Find leasing leads by the Russian tax id (INN).",
                "input_schema": {
                    "type": "object",
                    "properties": {"inn": {"type": "string"}},
                    "required": ["inn"],
                },
            },
            {
                "name": "lead_details",
                "description": "Get full details for one leasing lead by its numeric id.",
                "input_schema": {
                    "type": "object",
                    "properties": {"item_id": {"type": "integer"}},
                    "required": ["item_id"],
                },
            },
        ]

    @override
    def execute(self, name: str, args: dict[str, Any]) -> str:
        """Route the tool name to the local python method and cap the output size."""
        if name == "leads_by_stage":
            res = self.leads_by_stage(
                str(args.get("stage_id") or ""),
                cast(int, args.get("limit") or 20),
            )
        elif name == "count_in_stage":
            res = self.count_in_stage(str(args.get("stage_id") or ""))
        elif name == "search_by_inn":
            res = self.search_by_inn(str(args.get("inn") or ""))
        elif name == "lead_details":
            res = self.lead_details(cast(int, args.get("item_id") or 0))
        else:
            raise ValueError(f"Unknown Bitrix tool: {name}")
            
        return serialize_tool_result(res)

    def leads_by_stage(self, stage_id: str, limit: int = 20) -> list[dict[str, object]]:
        items = self._client.iter_items(
            ENTITY_TYPE_ID,
            filter={"stageId": stage_id},
            select=SELECT_KEYS,
            max_items=limit,
        )
        return [self._decode(item) for item in items]

    def count_in_stage(self, stage_id: str, max_count: int = 10000) -> dict[str, object]:
        count = 0
        for _ in self._client.iter_items(
            ENTITY_TYPE_ID,
            filter={"stageId": stage_id},
            select=["id"],
            max_items=max_count,
        ):
            count += 1
        return {
            "stageId": stage_id,
            "count": count,
            "truncated": count >= max_count,
        }

    def search_by_inn(self, inn: str, limit: int = 10) -> list[dict[str, object]]:
        items = self._client.iter_items(
            ENTITY_TYPE_ID,
            filter={"ufCrm31Inn": inn},
            select=SELECT_KEYS,
            max_items=limit,
        )
        return [self._decode(item) for item in items]

    def lead_details(self, item_id: int) -> dict[str, object]:
        return self._decode(self._client.item_get(ENTITY_TYPE_ID, item_id))
