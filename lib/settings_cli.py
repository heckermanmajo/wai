"""CLI fuer Settings setzen/lesen — Plan 03.

Beispiele:
    python -m lib.settings_cli set --scope platform \\
        --key agent.model.default --value '"gpt-5.4"'

    python -m lib.settings_cli set --scope tenant --tenant demo \\
        --key agent.model.default --value '"gpt-5.5"'

    python -m lib.settings_cli get --tenant demo --key agent.model.default

    python -m lib.settings_cli list --scope platform
    python -m lib.settings_cli list --scope tenant --tenant demo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from lib.db import session_for_admin, session_for_tenant  # noqa: E402
from lib.entities.admin.setting import Setting as AdminSetting  # noqa: E402
from lib.entities.tenant.setting import Setting as TenantSetting  # noqa: E402
from lib.settings import VALID_SCOPES, resolve, set_value  # noqa: E402


def _cmd_set(args: argparse.Namespace) -> int:
    try:
        value = json.loads(args.value)
    except json.JSONDecodeError as exc:
        print(f"FEHLER: --value ist kein valides JSON ({exc}).", file=sys.stderr)
        print('Beispiele:  --value \'"gpt-5.4"\'  |  --value 42  |  --value \'{"a":1}\'',
              file=sys.stderr)
        return 2

    # scope_ref Defaults wie im Plan beschrieben
    scope_ref = args.scope_ref or ""
    if args.scope == "tenant" and not scope_ref:
        if not args.tenant:
            print("FEHLER: --tenant noetig fuer scope=tenant.", file=sys.stderr)
            return 2
        scope_ref = args.tenant
    if args.scope == "entity_type" and not scope_ref:
        if not args.entity_cls:
            print("FEHLER: --entity-cls noetig fuer scope=entity_type.",
                  file=sys.stderr)
            return 2
        scope_ref = args.entity_cls
    if args.scope == "chat" and not scope_ref:
        if not args.chat_id:
            print("FEHLER: --chat-id noetig fuer scope=chat.", file=sys.stderr)
            return 2
        scope_ref = str(args.chat_id)

    set_value(
        args.key, value,
        scope=args.scope, scope_ref=scope_ref,
        entity_cls=args.entity_cls or "",
        entity_id=args.entity_id or 0,
        tenant=args.tenant,
        set_by=args.set_by or 0,
    )
    print(f"OK gesetzt: scope={args.scope} key={args.key} value={value!r}")
    return 0


def _cmd_get(args: argparse.Namespace) -> int:
    val = resolve(
        args.key,
        tenant=args.tenant,
        entity_cls=args.entity_cls,
        entity_id=args.entity_id,
        chat_id=args.chat_id,
    )
    print(json.dumps(val))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    if args.scope == "platform":
        with session_for_admin() as s:
            rows = s.execute(
                select(AdminSetting)
                .where(AdminSetting.scope == "platform")
                .where(AdminSetting.is_deleted.is_(False))
                .order_by(AdminSetting.key)
            ).scalars().all()
            for r in rows:
                print(f"{r.scope:12s} {r.scope_ref:24s} {r.key:40s} = "
                      f"{json.dumps(r.value)}")
        return 0
    if not args.tenant:
        print("FEHLER: --tenant noetig fuer non-platform list.", file=sys.stderr)
        return 2
    with session_for_tenant(args.tenant) as s:
        q = select(TenantSetting).where(TenantSetting.is_deleted.is_(False))
        if args.scope:
            q = q.where(TenantSetting.scope == args.scope)
        rows = s.execute(q.order_by(TenantSetting.scope, TenantSetting.key)).scalars().all()
        for r in rows:
            print(f"{r.scope:12s} {r.scope_ref:24s} {r.entity_cls:18s}"
                  f"#{r.entity_id:>4d} {r.key:40s} = {json.dumps(r.value)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lib.settings_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_set = sub.add_parser("set", help="Setting setzen (upsert).")
    p_set.add_argument("--scope", required=True, choices=VALID_SCOPES)
    p_set.add_argument("--scope-ref", default="")
    p_set.add_argument("--tenant", default=None)
    p_set.add_argument("--entity-cls", default="")
    p_set.add_argument("--entity-id", type=int, default=0)
    p_set.add_argument("--chat-id", type=int, default=0)
    p_set.add_argument("--key", required=True)
    p_set.add_argument("--value", required=True,
                       help='JSON-Wert, z.B. \'"gpt-5.4"\' oder 42')
    p_set.add_argument("--set-by", type=int, default=0)
    p_set.set_defaults(func=_cmd_set)

    p_get = sub.add_parser("get", help="Setting per Resolver lesen.")
    p_get.add_argument("--key", required=True)
    p_get.add_argument("--tenant", default=None)
    p_get.add_argument("--entity-cls", default=None)
    p_get.add_argument("--entity-id", type=int, default=None)
    p_get.add_argument("--chat-id", type=int, default=None)
    p_get.set_defaults(func=_cmd_get)

    p_list = sub.add_parser("list", help="Settings einer Schicht anzeigen.")
    p_list.add_argument("--scope", default=None,
                        choices=list(VALID_SCOPES))
    p_list.add_argument("--tenant", default=None)
    p_list.set_defaults(func=_cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
