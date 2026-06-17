# interface

**Status:** Leer — Tech-Stack noch zu entscheiden.

## Zweck
Tenant-facing Frontend. Rendert Chat (zum `manager`-Agent), dynamische Forms (vom `designer`), Views, Dashboards (vom `visualizer`).

## Offene Entscheidungen
- **Framework:** Angular (passt zu CLAUDE.md → `@basex/framework`)? React? Etwas anderes?
- **Auth:** OIDC gegen Admin-DB? Eigener Auth-Service?
- **Realtime:** WebSockets für Chat/Agent-Streaming
- **Form-Renderer:** generischer Renderer der `Form`-Schemas aus Tenant-DB darstellt

## Nicht-Ziele
- Keine Business-Logik im Frontend — alles geht über Gateway/Agents.
- Keine direkten DB-Zugriffe.

> Vor dem Sprouten: Ports interaktiv klären (CLAUDE.md-Regel) und in `package.json`/CORS festziehen.
