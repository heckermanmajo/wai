#!/usr/bin/env python3
"""test_all_mcp.py — MCP Integration Test Suite.

Liest die globalen und workspace-spezifischen MCP-Einstellungen ein,
startet jeden Server und validiert die Verbindung via JSON-RPC.
"""
import json
import os
import subprocess
import sys
import time

# Pfade zu den Einstellungen
GLOBAL_PATHS = [
    r"C:\Users\Theo\AppData\Roaming\Code\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json",
    r"C:\Users\Theo\AppData\Roaming\Antigravity\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json",
    r"C:\Users\Theo\AppData\Roaming\Antigravity IDE\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json"
]
LOCAL_PATH = r"c:\Users\Theo\Downloads\wai-main\.vscode\cline_mcp_settings.json"


def load_settings() -> dict:
    """Lädt und verschmilzt globale und lokale MCP-Server-Konfigurationen."""
    merged = {}
    # Lade globale Einstellungen
    for path in GLOBAL_PATHS:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                merged.update(json.load(f).get("mcpServers", {}))
        except Exception:
            continue
    # Lade lokale Einstellungen
    if os.path.exists(LOCAL_PATH):
        try:
            with open(LOCAL_PATH, "r", encoding="utf-8") as f:
                merged.update(json.load(f).get("mcpServers", {}))
        except Exception:
            pass
    return merged


def prepare_command(cmd: str) -> str:
    """Bereitet den Befehl für die Ausführung unter Windows vor (z.B. npx -> npx.cmd)."""
    if os.name == "nt" and cmd.lower() == "npx":
        return "npx.cmd"
    return cmd


def read_json_line(proc) -> dict:
    """Liest die nächste Zeile und parst sie als JSON, falls möglich."""
    line = proc.stdout.readline()
    if not line:
        return {"error": "Prozess beendet oder leere Antwort"}
    line = line.strip()
    if not line.startswith("{"):
        return {}
    try:
        data = json.loads(line)
        if "id" in data or "jsonrpc" in data:
            return data
    except json.JSONDecodeError:
        pass
    return {}


def execute_handshake(proc, req_id: int, method: str, params: dict) -> dict:
    """Sendet ein JSON-RPC Paket an stdin und liest die Antwort von stdout."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params
    }) + "\n"

    try:
        proc.stdin.write(payload)
        proc.stdin.flush()
    except Exception as e:
        return {"error": str(e)}

    # Ignoriere Log-Ausgaben auf stdout und finde das JSON-RPC-Paket
    for _ in range(50):
        res = read_json_line(proc)
        if "error" in res or res:
            return res
    return {"error": "Maximale Anzahl ungültiger Zeilen überschritten"}


def test_server(name: str, config: dict) -> dict:
    """Testet einen einzelnen MCP-Server durch Starten und Abfragen der Tools."""
    if config.get("disabled", False):
        return {"status": "DEAKTIVIERT", "tools": []}

    cmd = prepare_command(config.get("command", ""))
    env = {**os.environ, **config.get("env", {})}

    print(f"\n[+] Teste MCP-Server: '{name}'...", flush=True)
    try:
        proc = subprocess.Popen(
            [cmd] + config.get("args", []),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env
        )
        time.sleep(1.5)
        return run_handshakes(proc, name)
    except Exception as e:
        return {"status": f"FEHLER beim Starten: {e}", "tools": []}


def run_handshakes(proc, name: str) -> dict:
    """Führt die Handshakes nach erfolgreichem Start aus."""
    init_res = execute_handshake(proc, 1, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-test-suite", "version": "1.0.0"}
    })

    if "error" in init_res:
        proc.terminate()
        return {"status": f"FEHLER beim Handshake: {init_res['error']}", "tools": []}

    # Tools abfragen
    tools_res = execute_handshake(proc, 2, "tools/list", {})
    proc.terminate()

    if "error" in tools_res:
        return {"status": f"Handshake OK, Fehler bei tools/list: {tools_res['error']}", "tools": []}

    tool_list = tools_res.get("result", {}).get("tools", [])
    names = [t.get("name", "") for t in tool_list]
    return {"status": "ERFOLGREICH", "tools": names}


def main():
    """Hauptfunktion: Lädt Konfigurationen und führt die Tests aus."""
    servers = load_settings()
    if not servers:
        print("[X] Keine MCP-Server konfiguriert gefunden.", flush=True)
        sys.exit(1)

    results = {}
    for name, config in servers.items():
        results[name] = test_server(name, config)

    print("\n" + "=" * 50)
    print("   MCP INTEGRATION TEST ERGEBNISSE")
    print("" + "=" * 50)
    for name, res in results.items():
        status = res["status"]
        tools_count = len(res["tools"])
        print(f"Server: {name:<25} Status: {status:<15} Tools: {tools_count}", flush=True)
        if tools_count > 0:
            print(f"  Verfügbare Tools: {', '.join(res['tools'])}", flush=True)
    print("=" * 50)


if __name__ == "__main__":
    main()
