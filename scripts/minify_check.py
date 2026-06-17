#!/usr/bin/env python3
"""minify_check.py — Code-Minification & Elegance Check Gate.

Dieses Skript parst Python-Dateien mittels AST und sucht nach typischem "AI Slop":
1. Einrückungstiefe (Nesting) von Verzweigungen und Schleifen > 2
2. Funktionslängen > 25 Zeilen
3. Redundanten try-except Blöcken (Log & Re-raise)
4. Schleifen, die als List/Dict Comprehensions geschrieben werden können
5. Führt ruff zur automatischen Code-Bereinigung und Linter-Prüfung aus.
"""
import ast
import os
import subprocess
import sys


class SlopVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []
        self.current_depth = 0

    def visit_FunctionDef(self, node):
        # Längen-Check
        if hasattr(node, "end_lineno") and node.end_lineno:
            length = node.end_lineno - node.lineno + 1
            if length > 25:
                self.violations.append(
                    (node.lineno, f"Funktion '{node.name}' ist mit {length} Zeilen zu lang (max. erlaubt: 25). Bitte in kleinere Hilfsfunktionen aufteilen.")
                )
        
        # Tiefen-Check zurücksetzen für Funktionen
        old_depth = self.current_depth
        self.current_depth = 0
        self.generic_visit(node)
        self.current_depth = old_depth

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def _visit_nesting_node(self, node, node_type):
        self.current_depth += 1
        if self.current_depth > 2:
            self.violations.append(
                (node.lineno, f"{node_type}-Verschachtelungstiefe ist {self.current_depth} (max. erlaubt: 2). Bitte nutzen Sie Early Returns.")
            )
        self.generic_visit(node)
        self.current_depth -= 1

    def visit_If(self, node):
        self._visit_nesting_node(node, "If")

    def visit_For(self, node):
        # Check ob List Comprehension möglich ist (einfaches append in der Schleife)
        if (len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Call) and
            isinstance(node.body[0].value.func, ast.Attribute) and
            node.body[0].value.func.attr == "append"):
            self.violations.append(
                (node.lineno, "Einfache For-Schleife mit '.append()' gefunden. Bitte als kompakte List Comprehension schreiben.")
            )
        self._visit_nesting_node(node, "For")

    def visit_While(self, node):
        self._visit_nesting_node(node, "While")

    def visit_Try(self, node):
        # Redundanter log & re-raise Check in exception handlern
        for handler in node.handlers:
            if len(handler.body) != 2:
                continue
            first, second = handler.body[0], handler.body[1]
            if not (isinstance(first, ast.Expr) and isinstance(second, ast.Raise)):
                continue
            call = first.value
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and
                call.func.attr in {"error", "exception", "warning", "info", "log"}):
                self.violations.append(
                    (handler.lineno, "Redundanter try-except Block (Log & Re-raise). Verwende globale Exception-Handler im Gateway/Manager.")
                )
        self._visit_nesting_node(node, "Try")


def run_linter(file_path: str) -> bool:
    """Führt ruff mit Auto-Fixes auf der geänderten Datei aus."""
    print(f"Starte ruff Auto-Fixes für {file_path}...", flush=True)
    # Ruff ausführen und automatisch reparieren (z. B. ungenutzte Imports, Vereinfachungen)
    try:
        subprocess.run(
            ["ruff", "check", "--select", "I,F,E,W,PL,TRY,C4,SIM", "--fix", file_path],
            check=False,
            capture_output=True,
            text=True
        )
    except FileNotFoundError:
        # Falls ruff nicht installiert ist, überspringen wir das
        print("Warnung: 'ruff' Linter ist nicht installiert/verfügbar. Überspringe Linter-Prüfung.", flush=True)
        return True
    return True


def print_violations(file_path: str, violations: list) -> None:
    """Druckt die gefundenen Qualitätsverletzungen aus."""
    print(f"\n[X] QUALITÄTS-CHECK FEHLGESCHLAGEN für {file_path}:", flush=True)
    for line, msg in sorted(violations):
        print(f"  Zeile {line}: {msg}", flush=True)
    print("\nBitte refaktoriere den Code, um die Dichte- und Struktur-Regeln zu erfüllen!\n", flush=True)


def check_file(file_path: str) -> bool:
    """Parst die Python-Datei und führt AST-basierte Qualitäts-Checks durch."""
    if not file_path.endswith(".py"):
        return True

    print(f"Führe AST-Komplexitätsprüfung für {file_path} durch...", flush=True)
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read())
    except SyntaxError as e:
        print(f"SyntaxError in {file_path}: Zeile {e.lineno}: {e.msg}", flush=True)
        return False

    visitor = SlopVisitor()
    visitor.visit(tree)

    if visitor.violations:
        print_violations(file_path, visitor.violations)
        return False

    print("[OK] Alle Qualitäts-Checks bestanden! Der Code ist elegant und kompakt.", flush=True)
    return True


def main():
    if len(sys.argv) < 2:
        print("Nutzung: python scripts/minify_check.py <pfad_zur_python_datei>", flush=True)
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Fehler: Datei existiert nicht: {file_path}", flush=True)
        sys.exit(1)

    run_linter(file_path)
    if not check_file(file_path):
        sys.exit(1)


if __name__ == "__main__":
    main()
