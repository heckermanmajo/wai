"""Tenant-Slug-Erzeugung.

Slugs müssen ASCII [a-z0-9_] sein, weil sie als Postgres-DB-Namens-Suffix
verwendet werden (`tenant_<slug>`) und damit weder in Quotes noch in
Identifier-Escaping landen sollen.

Beispiele:
    "Gärtnerei Müller GmbH"  -> "gaertnerei_mueller_gmbh"
    "Foo-Bar 42"             -> "foo_bar_42"
    "  ___test___  "         -> "test"
"""
from __future__ import annotations

import re
import unicodedata

_UMLAUT_MAP = {
    "ä": "ae", "ö": "oe", "ü": "ue",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss",
}

_VALID = re.compile(r"^[a-z0-9_]+$")


def slugify_tenant(name: str) -> str:
    s = name
    for ch, repl in _UMLAUT_MAP.items():
        s = s.replace(ch, repl)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError(f"Slug aus Name {name!r} ist leer nach Normalisierung")
    return s


def is_valid_slug(slug: str) -> bool:
    return bool(_VALID.match(slug)) and not slug.startswith("_") and not slug.endswith("_")
