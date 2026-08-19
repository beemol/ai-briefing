from bitrix_client import BitrixClient

# The "Лизинг" smart process (dynamic CRM entity).
ENTITY_TYPE_ID = 168

# Fields we return by default. Trim before going live — avoid leaking PII.
SELECT_KEYS = [
    "id",
    "title",
    "stageId",
    "ufCrm31Inn",
    "ufCrm31Name",
    "ufCrm31PhoneNumber",
    "ufCrm31ConclusionHeadSc",
    "createdTime",
    "updatedTime",
]


class BitrixTools:
    """High-level, prompt-friendly operations over the leasing smart process."""

    def __init__(self, client: BitrixClient):
        self._client: BitrixClient = client
        self._enum_map: dict[str, dict[str, str]] = client.get_enum_map(ENTITY_TYPE_ID)

    def _decode(self, item: dict[str, object]) -> dict[str, object]:
        return self._client.decode_item(item, self._enum_map)

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
