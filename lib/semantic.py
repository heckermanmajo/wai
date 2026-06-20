"""SemanticResource-Protokoll und Helper fuer die semantische Schicht.

Die semantische Schicht haengt sich quer ueber fachliche Entities und
indiziert deren Markdown-Repraesentation in zwei Tabellen:

  - ``SemanticFassade``  — 1:1 zu jeder Quell-Entity, content_hash-gebunden.
                           Haelt Name/Abstract/URL und einen Hash, der die
                           letzte indizierte Version eindeutig identifiziert.
  - ``SemanticSnippet``  — Chunks der Markdown-Repraesentation, spaeter fuer
                           RAG/Embeddings. Aktuell nur Text und ein simpler
                           token_estimate; pgvector folgt in einer spaeteren
                           Migration.

Damit eine Entity-Klasse semantisch indiziert werden kann, muss sie das
``SemanticResource``-Protokoll erfuellen. Wir nutzen ``typing.Protocol``
bewusst statt einer abstrakten Basisklasse: SQLAlchemy-Models haben bereits
eine Metaclass (``DeclarativeMeta``), und ein zweiter abstrakter Mixin mit
ABCMeta wuerde Metaclass-Konflikte ausloesen. Das Protocol ist rein
strukturell (Duck-Typing) und vermeidet das Problem.

Jede ``SemanticResource`` traegt zusaetzlich eine Class-Konstante
``RESOURCE_SYSTEM_EXPLANATION`` — ein kurzer Klartext, der LLMs erklaert,
was diese Resource semantisch ist (z.B. "Ein Document ist ein eigenstaendiges
Markdown-Dokument im Tenant"). Wir koennen das spaeter ueber alle registrierten
Resource-Klassen einsammeln und einem System-Prompt beifuegen.
"""
from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable


@runtime_checkable
class SemanticResource(Protocol):
    """Strukturelles Protokoll fuer indizierbare Tenant-Entities.

    Implementierungen leben auf den Entity-Klassen selbst (z.B. ``Document``,
    ``Note``, ``Task``). Wir verzichten auf eine abstrakte Basisklasse, um
    SQLAlchemy-Metaclass-Konflikte zu vermeiden.

    Die ``id``-Property kommt automatisch ueber ``BaseMixin`` mit, ist hier
    nur als Hint fuer den Type-Checker deklariert.
    """

    id: int

    RESOURCE_SYSTEM_EXPLANATION: str

    def get_resource_type(self) -> str:
        """Stabiler kurzer Resource-Typ-Slug, z.B. ``"document"``, ``"note"``."""
        ...

    def get_resource_name(self) -> str:
        """Anzeige-Titel fuer die Fassade (kurz, eine Zeile)."""
        ...

    def get_resource_short(self) -> str:
        """Ein-Zeilen-Abstract / Teaser fuer Listen-Ansichten (max ~200 Zeichen)."""
        ...

    def get_resource_markdown(self) -> str:
        """Vollstaendige Markdown-Repraesentation, die indiziert wird."""
        ...

    def get_resource_url(self) -> str:
        """UI-Pfad zur Detail-Ansicht, OHNE Tenant-Slug-Praefix."""
        ...


def compute_content_hash(name: str, markdown: str) -> str:
    """SHA256 ueber ``name + "\\0" + markdown`` als hex-String.

    Wir nehmen Name und Body in den Hash mit auf, weil der Fassade-Titel
    auch durch die ``name``-Aenderung neu indiziert werden soll, selbst
    wenn der Body identisch bleibt (z.B. nur Umbenennung des Documents).
    """
    h = hashlib.sha256()
    h.update((name or "").encode("utf-8"))
    h.update(b"\x00")
    h.update((markdown or "").encode("utf-8"))
    return h.hexdigest()
