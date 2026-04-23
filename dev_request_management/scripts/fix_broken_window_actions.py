#!/opt/odoo19/venv19/bin/python3
# -*- coding: utf-8 -*-
import argparse
import os
import re
import sys


def bootstrap_odoo():
    sys.path.append("/opt/odoo19/server")
    import odoo
    from odoo import api, SUPERUSER_ID

    return odoo, api, SUPERUSER_ID


def patch_server_actions(env):
    fixed = []
    actions = env["ir.actions.server"].sudo().search(
        [("state", "=", "code"), ("code", "ilike", "records.action_")]
    )
    for action in actions:
        code = action.code or ""
        patched = re.sub(
            r"\brecords\.(action_[A-Za-z0-9_]+)\(\)",
            r"(records or env.user).\1()",
            code,
        )
        if patched != code:
            fixed.append((action.id, action.name, code.strip(), patched.strip()))
            action.write({"code": patched})
    return fixed


def fix_broken_window_actions(env):
    fixed = []
    actions = env["ir.actions.act_window"].sudo().search([("res_id", "!=", False)])
    for action in actions:
        model_name = action.res_model
        is_broken = not model_name or model_name not in env or not env[model_name].sudo().browse(action.res_id).exists()
        if is_broken:
            fixed.append((action.id, action.name, model_name, action.res_id))
            action.write({"res_id": False})
    return fixed


def main():
    parser = argparse.ArgumentParser(description="Fix broken Odoo window actions safely.")
    parser.add_argument("-d", "--database", required=True, help="Database name")
    parser.add_argument("-c", "--config", default="/opt/odoo19/odoo19.conf", help="Odoo config path")
    args = parser.parse_args()

    odoo, api, superuser_id = bootstrap_odoo()
    odoo.tools.config.parse_config(["-c", args.config, "-d", args.database])
    registry = odoo.modules.registry.Registry(args.database)
    with registry.cursor() as cr:
        env = api.Environment(cr, superuser_id, {})

        fixed_windows = fix_broken_window_actions(env)
        fixed_servers = patch_server_actions(env)
        cr.commit()

        print("Broken ir.actions.act_window fixed:")
        if fixed_windows:
            for action_id, name, model_name, broken_res_id in fixed_windows:
                print(f"- id={action_id} name={name} model={model_name} broken_res_id={broken_res_id}")
        else:
            print("- none")

        print("\nUnsafe ir.actions.server code patched:")
        if fixed_servers:
            for action_id, name, before, after in fixed_servers:
                print(f"- id={action_id} name={name}")
                print(f"  before: {before}")
                print(f"  after:  {after}")
        else:
            print("- none")


if __name__ == "__main__":
    main()
