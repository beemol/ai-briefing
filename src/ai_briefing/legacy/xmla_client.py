import os
import xml.etree.ElementTree as ET
from typing import final
from xml.sax.saxutils import escape

import requests

from ai_briefing.domain.powerbi.auth import get_access_token

XMLA_NS = "urn:schemas-microsoft-com:xml-analysis"
ROWSET_NS = "urn:schemas-microsoft-com:xml-analysis:rowset"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"


@final
class XmlaClient:
    """Query a Power BI model over the raw XMLA endpoint (HTTP SOAP).

    The REST executeQueries API only allows data DAX queries; the raw XMLA
    endpoint additionally serves metadata queries like $SYSTEM.TMSCHEMA_TABLES.

    NOTE: XMLA endpoints exist only on Premium / Premium Per User / Embedded
    capacities. On shared capacity (this workspace) the URL serves the REST
    API and rejects SOAP POST with HTTP 405.
    """

    def __init__(self, access_token: str, endpoint: str):
        self._token: str = access_token
        self._endpoint: str = endpoint

    def execute(self, statement: str, catalog: str) -> list[dict[str, str]]:
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="{SOAP_NS}" SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<SOAP-ENV:Body>
<Execute xmlns="{XMLA_NS}" SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<Command><Statement>{escape(statement)}</Statement></Command>
<Properties><PropertyList><Catalog>{escape(catalog)}</Catalog><Timeout>3600</Timeout></PropertyList></Properties>
</Execute>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

        res = requests.post(
            self._endpoint,
            data=body.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f"{XMLA_NS}:Execute",
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"XMLA HTTP {res.status_code}: {res.text[:2000]}")

        try:
            root = ET.fromstring(res.content)
        except ET.ParseError as exc:
            raise RuntimeError(f"XMLA response is not XML: {exc}\n{res.text[:2000]}")

        fault = root.find(f".//{{{SOAP_NS}}}Fault")
        if fault is not None:
            raise RuntimeError(
                "XMLA fault: " + ET.tostring(fault, encoding="unicode")[:2000]
            )

        rows: list[dict[str, str]] = []
        for row in root.iter(f"{{{ROWSET_NS}}}row"):
            cells = {
                child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
                for child in row
            }
            rows.append(cells)
        return rows


if __name__ == "__main__":
    tenant_id = os.getenv("TENANT_ID", "")
    workspace_id = os.getenv("WORKSPACE_ID", "")
    dataset_name = os.getenv("DATASET_NAME", "Воронка Лизинг_5.0")
    if not tenant_id or not workspace_id:
        raise SystemExit("Missing TENANT_ID or WORKSPACE_ID")

    endpoint = os.getenv(
        "XMLA_ENDPOINT",
        f"https://api.powerbi.com/v1.0/{tenant_id}/groups/{workspace_id}",
    )
    client = XmlaClient(get_access_token(), endpoint)

    print("=== TABLES ($SYSTEM.TMSCHEMA_TABLES) ===")
    for row in client.execute("SELECT * FROM $SYSTEM.TMSCHEMA_TABLES", dataset_name):
        print(row)

    print("\n=== COLUMNS ($SYSTEM.TMSCHEMA_COLUMNS) ===")
    for row in client.execute("SELECT * FROM $SYSTEM.TMSCHEMA_COLUMNS", dataset_name):
        print(row)
