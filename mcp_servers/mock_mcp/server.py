"""Lead-Manager-Mock — FastMCP SSE server with 3 lead tools.

Tools:
  hole_kunden_status  — look up a customer by name
  erstelle_kunden_notiz — append a note, auto-create if missing
  suche_kunden        — substring search across customers
"""
import os

from mcp.server.fastmcp import FastMCP

from lib.logging import get_logger

logger = get_logger(__name__)

KUNDEN_DB: dict[str, dict] = {
    "meier": {"projekt": "Dachsanierung", "status": "Wartet auf Material", "rechnung_offen": True, "notizen": []},
    "schmidt": {"projekt": "Heizungswartung", "status": "Abgeschlossen", "rechnung_offen": False, "notizen": []},
    "mueller": {"projekt": "Badrenovierung", "status": "In Arbeit", "rechnung_offen": True, "notizen": []},
}

mcp = FastMCP("lead-manager-mock", port=8001)


@mcp.tool()
def hole_kunden_status(kunden_name: str) -> str:
    key = kunden_name.lower().strip()
    kunde = KUNDEN_DB.get(key)
    if not kunde:
        return f"Fehler: Kein Kunde namens '{kunden_name}' im System gefunden."
    offen = "Ja" if kunde["rechnung_offen"] else "Nein"
    return f"Kunde '{key.title()}': Projekt '{kunde['projekt']}', Status: {kunde['status']}, Rechnung offen: {offen}"


@mcp.tool()
def erstelle_kunden_notiz(kunden_name: str, notiz: str) -> str:
    key = kunden_name.lower().strip()
    kunde = KUNDEN_DB.get(key)
    if not kunde:
        KUNDEN_DB[key] = {"projekt": "Unbekannt", "status": "Neu", "rechnung_offen": False, "notizen": []}
        kunde = KUNDEN_DB[key]
        logger.info("auto-create kunde=%s", key)
    kunde["notizen"].append(notiz)
    logger.info("notiz_gespeichert kunde=%s notiz=%r", key, notiz)
    return f"✅ Notiz zu '{key.title()}' gespeichert: '{notiz}'"


@mcp.tool()
def suche_kunden(name_teil: str) -> str:
    term = name_teil.lower().strip()
    treffer = [f"- {n.title()} ({d['projekt']})" for n, d in KUNDEN_DB.items() if term in n]
    if not treffer:
        return "Keine Kunden gefunden."
    return "Gefundene Kunden:\n" + "\n".join(treffer)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    logger.info("Starte Lead-Manager-Mock auf Port %s via SSE", port)
    mcp.run(transport="sse")
