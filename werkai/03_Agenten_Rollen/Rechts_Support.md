# 🤖 Rechts-Support (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Rechts-Support unterstützt das Handwerksbüro bei rechtlichen und regulatorischen Fragestellungen, insbesondere bezüglich Verträgen, DIN-Normen, VOB (Vergabe- und Vertragsordnung für Bauleistungen) und DSGVO-Compliance.

## 2. Aufgaben & Fähigkeiten
- **Vertragsprüfung**: Durchsicht von Verträgen und Ausschreibungen auf Risikoklauseln oder ungewöhnliche Gewährleistungsfristen.
- **Normen-Check**: Unterstützung bei der Identifikation und Interpretation relevanter DIN-Normen für Bauprojekte (RAG-basiertes System).
- **Compliance-Überwachung**: Überprüfung, ob interne Datenflüsse und Speicherungen den DSGVO-Richtlinien entsprechen.

## 3. Tooling & Integrationen
- **RAG-Wissensdatenbank**: Vektordatenbank (pgvector in PostgreSQL) mit rechtlichen Dokumenten, Normen-Katalogen und Musterverträgen.
- **LLM-Nutzung**: Tier 2 LLMs (aufgrund der hohen Komplexität rechtlicher Texte) mit striktem Zero-Data-Retention-Agreement.
- **Schnittstelle**: Bereitstellung von Warnungen und Formulierungshilfen in Baserow.
