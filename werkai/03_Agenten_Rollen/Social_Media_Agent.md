# 🤖 Social-Media-Agent (Semantischer Mitarbeiter)

## 1. Rolle & Zielsetzung
Der Social-Media-Agent managed den Online-Auftritt des Handwerksbetriebs (z.B. Instagram, Facebook), um neue Kunden und Auszubildende/Mitarbeiter zu gewinnen.

## 2. Aufgaben & Fähigkeiten
- **Content-Erstellung**: Generierung von Entwürfen für Posts, Bildbeschreibungen und Hashtags auf Basis aktueller Baustellenberichte.
- **Bildgenerierung**: Unterstützung des [[Designer_Agent|Designer-Agenten]] bei der Bildbearbeitung oder autonomen Bilderzeugung für Marketingkampagnen.
- **Schnittstellen-Nutzung**: Zugriff auf Meta-APIs zur Platzierung von Postings (im Entwurfsmodus).

## 3. Tooling & Integrationen
- **Meta Graph API**: Anbindung an Facebook/Instagram-Unternehmenskonten (via n8n).
- **Bildgenerierung**: Schnittstellen zu Dall-E 3 oder Stable Diffusion.
- **Freigabe**: Alle Social-Media-Beiträge werden als Entwürfe in Baserow abgelegt und müssen vom Inhaber freigegeben werden.
