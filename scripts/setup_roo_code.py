#!/usr/bin/env python3
"""setup_roo_code.py — Automatisches Onboarding-Skript für Roo Code Setup.

Dieses Skript richtet die globalen MCP-Server-Einstellungen für Team-Mitglieder
auf Windows, macOS und Linux ein. Es passt die Pfade dynamisch an das lokale System an.
"""
import json
import os
import sys

# Standardmäßige Serverdefinitionen (mit Platzhaltern)
SERVER_DEFS = {
    "codet5-jepa": {
        "command": "{python_bin}",
        "args": ["{parent_dir}/code t5+/jepa_mcp_server.py"],
        "disabled": False,
        "alwaysAllow": [
            "semantic_code_search",
            "multi_query_search",
            "tree_mapping",
            "generate_jepa_plan",
            "suggest_code",
            "diff_merge_code",
            "batch_train",
            "register_accepted_sample",
            "show_jepa_status",
            "reset_jepa_predictor"
        ]
    },
    "local-router": {
        "command": "{python_bin}",
        "args": ["{parent_dir}/mcp/local-router/server.py"],
        "disabled": False,
        "alwaysAllow": [
            "compress_context",
            "classify_task",
            "build_deepseek_packet",
            "summarize_result",
            "build_memory_update",
            "translate_to_professional"
        ]
    },
    "code-understanding": {
        "command": "{python_bin}",
        "args": ["{parent_dir}/mcp/code-understanding/server.py"],
        "disabled": False,
        "alwaysAllow": [
            "semantic_code_search",
            "summarize_code_snippet",
            "find_similar_implementation"
        ]
    },
    "obsidian-brain": {
        "command": "{python_bin}",
        "args": ["{parent_dir}/mcp/obsidian/server.py"],
        "disabled": False,
        "env": {
            "OBSIDIAN_VAULT_PATH": "{parent_dir}/obsidian-vault"
        },
        "alwaysAllow": [
            "read_note",
            "search_notes",
            "write_memory_entry",
            "append_to_note"
        ]
    },
    "semantic-code-translator": {
        "command": "npx",
        "args": [
            "-y",
            "tsx",
            "{parent_dir}/semantic-code-translator-mcp/src/mcp/server.ts"
        ],
        "disabled": False,
        "alwaysAllow": [
            "get_compressed_file",
            "detect_leakage",
            "reset_session",
            "analyze_symbols",
            "build_mapping",
            "compress_context"
        ]
    },
    "codebase-index": {
        "command": "{python_bin}",
        "args": ["-m", "mcp_codebase_index.server"],
        "disabled": False,
        "alwaysAllow": [
            "get_project_summary",
            "list_files",
            "get_structure_summary",
            "get_functions",
            "get_classes",
            "get_imports",
            "get_function_source",
            "get_class_source",
            "find_symbol",
            "get_dependencies",
            "get_dependents",
            "get_change_impact",
            "get_call_chain",
            "get_file_dependencies",
            "get_file_dependents",
            "search_codebase",
            "reindex",
            "get_usage_stats"
        ]
    }
}


def get_global_settings_paths() -> list[str]:
    """Gibt die plattformspezifischen Pfade zur globalen mcp_settings.json zurück."""
    paths = []
    home = os.path.expanduser("~")
    # Definiere AppData Ordner für verschiedene IDEs
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        paths.append(os.path.join(appdata, r"Code\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json"))
        paths.append(os.path.join(appdata, r"Antigravity\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json"))
        paths.append(os.path.join(appdata, r"Antigravity IDE\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json"))
    else:
        # macOS / Linux Fallbacks
        paths.append(os.path.join(home, "Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json"))
        paths.append(os.path.join(home, ".config/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json"))
    return paths


def get_python_binary(parent_dir: str) -> str:
    """Ermittelt den Pfad zur Python-Executable im Virtualenv."""
    bin_name = "python.exe" if os.name == "nt" else "python"
    script_dir = "Scripts" if os.name == "nt" else "bin"
    return os.path.normpath(os.path.join(parent_dir, ".venv", script_dir, bin_name))


def parse_and_fill_template(parent_dir: str) -> dict:
    """Erzeugt die finalen Serverdefinitionen mit angepassten Pfaden."""
    python_bin = get_python_binary(parent_dir)
    filled = {}
    
    for name, config in SERVER_DEFS.items():
        # Kopie erstellen
        item = json.loads(json.dumps(config))
        # Platzhalter ersetzen
        item["command"] = item["command"].replace("{python_bin}", python_bin)
        item["args"] = [a.replace("{parent_dir}", parent_dir) for a in item["args"]]
        if "env" in item:
            item["env"] = {k: v.replace("{parent_dir}", parent_dir) for k, v in item["env"].items()}
        filled[name] = item
        
    return filled


def update_settings_file(path: str, new_servers: dict) -> None:
    """Integriert die neuen Serverdefinitionen in eine existierende Einstellungsdatei."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {"mcpServers": {}}
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"mcpServers": {}}

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    data["mcpServers"].update(new_servers)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"[OK] Einstellungen erfolgreich aktualisiert: {path}")


def update_all_paths(paths: list, new_servers: dict) -> bool:
    """Aktualisiert alle gefundenen globalen Einstellungsdateien."""
    updated = False
    for path in paths:
        try:
            update_settings_file(path, new_servers)
            updated = True
        except Exception as e:
            print(f"[Warnung] Konnte Datei nicht aktualisieren ({path}): {e}")
    return updated


def main():
    """Startet das Onboarding-Setup für Roo Code."""
    print("=" * 60 + "\n   ROO CODE SETUP & ONBOARDING HELPER\n" + "=" * 60)
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    detected_parent = os.path.dirname(project_root)
    print(f"Erkannter Projektpfad: {project_root}\nErkanntes Stammverzeichnis: {detected_parent}")
    
    parent_dir = input(f"\nStammverzeichnis eingeben [Standard: {detected_parent}]: ").strip()
    parent_dir = os.path.abspath(parent_dir or detected_parent).replace("\\", "/")
    
    new_servers = parse_and_fill_template(parent_dir)
    
    if not update_all_paths(get_global_settings_paths(), new_servers):
        print("\n[!] Keine globalen Roo Code Speicherpfade gefunden. Bitte stelle sicher, dass Roo Code installiert ist.")
        sys.exit(1)

    print("\n[OK] Setup vollständig abgeschlossen!\nRoo Code wird nun verknüpft.")


if __name__ == "__main__":
    main()
