"""Login-Page fuer das wai-Gateway.

Wird gerendert unter `/login` (global, kein Tenant im Pfad). Der User
gibt Username oder Email + Passwort ein; der Tenant wird beim POST
serverseitig ueber die TenantMembership des Users aufgeloest:
    - genau 1 Tenant  -> direkter Redirect auf /<slug>/
    - mehrere Tenants -> Picker-Page (render_tenant_picker)
    - keine Tenants   -> Fehler

Daneben listet die Page (Dev-Modus) alle bekannten User mit Username,
Email und ihren Tenants — alle teilen sich das Dev-Passwort "123".
Klick auf einen User trafgt den Login-Wert ins Formular.
"""
from html import escape

DEV_PASSWORD = "123"


def _render_dev_users(dev_users: list[dict]) -> str:
    if not dev_users:
        return ""
    rows: list[str] = []
    for u in dev_users:
        username = escape(u.get("username", ""))
        email = escape(u.get("email", "") or "")
        tenants = ", ".join(escape(t) for t in u.get("tenants") or []) or "—"
        display = escape(u.get("display_name", "") or u.get("username", ""))
        rows.append(
            f"""
            <div class="dev-user" data-login="{username}">
              <div class="dev-user-main">
                <span class="dev-user-name">{display}</span>
                <span class="dev-user-tenants">{tenants}</span>
              </div>
              <div class="dev-user-creds">
                <code class="copy" data-copy="{username}">{username}</code>
                <code class="copy" data-copy="{email}">{email or '—'}</code>
              </div>
            </div>"""
        )
    return f"""
    <div class="dev-card">
      <div class="dev-head">
        <h2>Dev-Accounts</h2>
        <div class="dev-pw">Passwort fuer alle: <code class="copy" data-copy="{DEV_PASSWORD}">{DEV_PASSWORD}</code></div>
      </div>
      <div class="dev-users">{''.join(rows)}</div>
      <div class="dev-hint">Klick auf einen Eintrag fuellt das Login-Feld unten aus.</div>
    </div>"""


def render_login(error: str = "", dev_users: list[dict] | None = None, prefill: str = "") -> str:
    safe_error = escape(error) if error else ""
    err_block = f'<div class="error">{safe_error}</div>' if safe_error else ""
    safe_prefill = escape(prefill or "")
    dev_block = _render_dev_users(dev_users or [])
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<title>wai - login</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    font: 14px/1.5 -apple-system, system-ui, sans-serif;
    margin: 0; background: #0e0f12; color: #e8eaed;
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }}
  .wrap {{ display: flex; flex-direction: column; gap: 16px; width: 440px; max-width: 100%; }}
  .card {{
    background: #16181d; border: 1px solid #25262b; border-radius: 10px;
    padding: 22px 26px; box-shadow: 0 12px 40px rgba(0,0,0,0.5);
  }}
  h1 {{ margin: 0 0 4px; font-size: 18px; font-weight: 600; }}
  .sub {{ color: #7c818b; font-size: 12px; margin-bottom: 18px; }}
  label {{ display: block; font-size: 11px; color: #9aa0aa; margin: 10px 0 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
  input[type=text], input[type=password] {{
    width: 100%; padding: 10px 12px; border-radius: 6px;
    border: 1px solid #2d2f36; background: #1a1c20; color: #e8eaed;
    font: inherit;
  }}
  input:focus {{ outline: none; border-color: #4669ff; }}
  button.primary {{
    margin-top: 18px; width: 100%; padding: 10px 18px;
    border: none; border-radius: 6px; background: #4669ff; color: white;
    font-weight: 600; font-size: 14px; cursor: pointer;
  }}
  button.primary:hover {{ background: #5a78ff; }}
  .error {{
    background: #2a1818; border: 1px solid #5a2a2a; color: #f4a4a4;
    border-radius: 6px; padding: 8px 12px; font-size: 12px; margin-bottom: 12px;
  }}

  /* Dev-Card */
  .dev-card {{
    background: #0c0d10; border: 1px dashed #3a3d46; border-radius: 10px;
    padding: 14px 18px; font-size: 12px;
  }}
  .dev-head {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #1c1d22;
  }}
  .dev-head h2 {{
    margin: 0; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.08em; color: #7c818b; font-weight: 600;
  }}
  .dev-pw {{ color: #9aa0aa; }}
  .dev-pw code {{ background: #1a1c20; color: #cfe1ff; padding: 2px 8px; border-radius: 4px; margin-left: 4px; font-weight: 600; }}
  .dev-users {{ display: flex; flex-direction: column; gap: 6px; }}
  .dev-user {{
    display: flex; flex-direction: column; gap: 4px;
    padding: 8px 10px; background: #14161a; border-radius: 6px;
    border: 1px solid #1c1d22; cursor: pointer;
  }}
  .dev-user:hover {{ background: #1a1c20; border-color: #2d2f36; }}
  .dev-user-main {{
    display: flex; justify-content: space-between; align-items: center; gap: 8px;
  }}
  .dev-user-name {{ font-weight: 600; color: #e8eaed; }}
  .dev-user-tenants {{ color: #7c818b; font-family: ui-monospace, monospace; font-size: 11px; }}
  .dev-user-creds {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .dev-user-creds code {{
    background: #0a0b0e; color: #c5cad3; padding: 2px 8px; border-radius: 4px;
    font-family: ui-monospace, monospace; font-size: 11px;
  }}
  .copy {{ cursor: copy; }}
  .copy:hover {{ background: #4669ff !important; color: white !important; }}
  .copied {{ background: #1f3a26 !important; color: #7ed99c !important; }}
  .dev-hint {{ color: #7c818b; font-size: 11px; margin-top: 10px; font-style: italic; }}
</style>
</head>
<body>
<div class="wrap">
  <form class="card" method="post" action="/login">
    <h1>Bei wai anmelden</h1>
    <div class="sub">Username oder Email + Passwort. Tenant wird automatisch erkannt.</div>
    {err_block}
    <label for="login">Username oder Email</label>
    <input id="login" name="login" type="text" autocomplete="username" autofocus required value="{safe_prefill}" />
    <label for="password">Passwort</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required />
    <button class="primary" type="submit">Anmelden</button>
  </form>
  {dev_block}
</div>
<script>
  const loginInput = document.getElementById('login');
  document.querySelectorAll('.dev-user').forEach(row => {{
    row.addEventListener('click', (e) => {{
      const code = e.target.closest('code.copy');
      if (code) return;  // copy-Buttons hatten eigenen Handler
      loginInput.value = row.dataset.login || '';
      loginInput.focus();
    }});
  }});
  document.querySelectorAll('code.copy').forEach(code => {{
    code.addEventListener('click', async (e) => {{
      e.stopPropagation();
      const txt = code.dataset.copy || code.textContent;
      try {{
        await navigator.clipboard.writeText(txt);
        code.classList.add('copied');
        setTimeout(() => code.classList.remove('copied'), 600);
      }} catch (_) {{}}
    }});
  }});
</script>
</body>
</html>
"""


def render_tenant_picker(
    pending_token: str,
    tenants: list[tuple[str, str]],
    error: str = "",
) -> str:
    safe_token = escape(pending_token)
    safe_error = escape(error) if error else ""
    err_block = f'<div class="error">{safe_error}</div>' if safe_error else ""
    rows = "".join(
        f"""
        <form method="post" action="/login/pick">
          <input type="hidden" name="token" value="{safe_token}" />
          <input type="hidden" name="tenant_slug" value="{escape(slug)}" />
          <button type="submit" class="tenant-btn">
            <span class="tn-name">{escape(name)}</span>
            <span class="tn-slug">{escape(slug)}</span>
          </button>
        </form>"""
        for slug, name in tenants
    )
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<title>wai - tenant waehlen</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{
    font: 14px/1.5 -apple-system, system-ui, sans-serif;
    margin: 0; background: #0e0f12; color: #e8eaed;
    min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px;
  }}
  .card {{
    background: #16181d; border: 1px solid #25262b; border-radius: 10px;
    padding: 22px 26px; width: 420px; max-width: 100%;
  }}
  h1 {{ margin: 0 0 4px; font-size: 18px; }}
  .sub {{ color: #7c818b; font-size: 12px; margin-bottom: 18px; }}
  .error {{
    background: #2a1818; border: 1px solid #5a2a2a; color: #f4a4a4;
    border-radius: 6px; padding: 8px 12px; font-size: 12px; margin-bottom: 12px;
  }}
  .tenant-btn {{
    display: flex; justify-content: space-between; align-items: center;
    width: 100%; padding: 12px 14px; margin-top: 8px;
    background: #1a1c20; border: 1px solid #2d2f36; border-radius: 6px;
    color: #e8eaed; cursor: pointer; font: inherit;
  }}
  .tenant-btn:hover {{ background: #1f2532; border-color: #4669ff; }}
  .tn-name {{ font-weight: 600; }}
  .tn-slug {{ color: #7c818b; font-family: ui-monospace, monospace; font-size: 11px; }}
  form {{ margin: 0; }}
</style>
</head>
<body>
<div class="card">
  <h1>Tenant waehlen</h1>
  <div class="sub">Du bist Mitglied in mehreren Tenants — bitte einen waehlen.</div>
  {err_block}
  {rows}
</div>
</body>
</html>
"""
