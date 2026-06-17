# 🧠 MASTER SYSTEM CONTEXT: WERK AI VAULT
*Single Source of Truth für Handwerk AI Multi-Agenten-Infrastruktur*

Willkommen im zentralen Wissens- und Architekturspeicher unseres Systems. Dieses Gehirn regelt die Ausrichtung, Entwicklung und den Betrieb der Handwerk AI Automationsplattform.

---

## 🧭 Vault-Navigation & Systemkarte

| Bereich | Dokument | Kurzbeschreibung |
| :--- | :--- | :--- |
| **Philosophie & Vision** | 🎯 **[[01_Vision_und_Prinzipien\|Vision & Prinzipien]]** | Das Fundament. Warum wir tun, was wir tun (Bürokratieabbau, Trojaner-Pitch, DSGVO). |
| **System-Architektur** | 🏗️ **[[02_Architektur_und_TechStack\|Architektur & Tech-Stack]]** | Hosting, Container-Strukturen, n8n-Integration, dynamisches LLM-Routing (Tier 1 vs. Tier 2). |
| **Daten & Struktur** | 🗄️ **[[06_Datenbank_Modell\|Datenbank-Modell (ERD)]]** | Relationales, mandantenfähiges PostgreSQL-Schema mit detaillierten Tabellenbeschreibungen. |
| **Schnittstellen** | 🔌 **[[04_MCP_Schnittstellen\|MCP-Schnittstellen (Registry)]]** | Schnittstellenregeln und Details zu den aktiven Entwicklungs- und Business-MCP-Servern. |
| **Agenten-Kollektiv** | 🤖 **[[03_Agenten_Rollen/Posteingangs_Agent\|Semantische Mitarbeiter]]** | Detaillierte Rollendefinitionen der 13 spezialisierten KI-Agenten (E-Mail, Finance, HR, etc.). |
| **Entwicklungs-Hub** | 💻 **[[05_Coding_Guidelines\|Coding Guidelines & Quality Gate]]** | Anti-Slop Directive, Code-Dichte Regeln und das AST-basierte Python-Quality-Gate. |
| **Betrieb & Ops** | ⚙️ **[[07_Operations_Runbook\|Operations & Deployment Runbook]]** | Docker Compose Setups, Traefik SSL-Zertifikate, Backup-Abläufe und Mandanten-Provisionierung. |

---

## 🛠️ Leitfaden für KI-Agenten (Developer Instructions)

> [!IMPORTANT]
> Bevor du eine Code-Änderung in diesem Repository planst oder vornimmst:
> 1. **Architektur-Check**: Lies [[02_Architektur_und_TechStack]] und [[06_Datenbank_Modell]], um sicherzustellen, dass dein Plan datenschutzkonform und datenbankseitig abgedeckt ist.
> 2. **Coding-Check**: Halte dich bedingungslos an die Richtlinien in [[05_Coding_Guidelines]] (Anti-Slop, maximal 2 Ebenen Nesting, maximal 25 Zeilen pro Funktion).
> 3. **Sync-Check**: Jede funktionale Erweiterung (z.B. neue Agenten-Tools) **MUSS** im entsprechenden Dokument unter `03_Agenten_Rollen/` oder `04_MCP_Schnittstellen.md` nachgepflegt werden.
