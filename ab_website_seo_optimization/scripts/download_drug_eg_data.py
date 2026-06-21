#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ODOO_SERVER_PATH = "/opt/odoo19/server"
if ODOO_SERVER_PATH not in sys.path and Path(ODOO_SERVER_PATH).exists():
    sys.path.insert(0, ODOO_SERVER_PATH)

import odoo
import odoo.service.server
from odoo import api, SUPERUSER_ID
from odoo.tools import config


DEFAULT_API_URL = "https://ready-api.vercel.app/api/drugs-eg"
DEFAULT_STATE_KEY = "ab_website_seo_optimization.drug_eg_import_state"


def parse_args():
    parser = argparse.ArgumentParser(description="Download Drug-EG API data into Odoo.")
    parser.add_argument("-c", "--config", default="/opt/odoo19/odoo19.conf", help="Odoo config file.")
    parser.add_argument("-d", "--database", required=True, help="Odoo database name.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Drug-EG API endpoint.")
    parser.add_argument("--api-key", required=True, help="Ready API bearer token.")
    parser.add_argument("--page-size", type=int, default=100, help="API page size, max 100.")
    parser.add_argument("--max-pages", type=int, default=0, help="Stop after N pages. Zero means all pages.")
    parser.add_argument("--max-requests", type=int, default=290, help="Safety cap for free-tier requests. Use 0 for no cap.")
    parser.add_argument("--search", default="", help="Optional API search term.")
    parser.add_argument("--manufacturer", default="", help="Optional manufacturer filter.")
    parser.add_argument("--route", default="", help="Optional route filter.")
    parser.add_argument("--price-min", type=float, default=None, help="Optional minimum EGP price.")
    parser.add_argument("--price-max", type=float, default=None, help="Optional maximum EGP price.")
    parser.add_argument("--sort", default="", help="Optional sort field supported by the API.")
    parser.add_argument("--order", choices=["asc", "desc"], default="", help="Optional sort order.")
    parser.add_argument("--request-delay", type=float, default=0.25, help="Seconds to wait between API requests.")
    parser.add_argument("--state-key", default=DEFAULT_STATE_KEY, help="ir.config_parameter key used for import checkpoint.")
    parser.add_argument("--reset-state", action="store_true", help="Clear the saved checkpoint and start from page 1.")
    parser.add_argument("--status", action="store_true", help="Print the saved checkpoint and exit.")
    return parser.parse_args()


def build_query(args, page):
    query = {
        "page": page,
        "limit": min(max(args.page_size, 1), 100),
    }
    optional = {
        "search": args.search,
        "manufacturer": args.manufacturer,
        "route": args.route,
        "price_min": args.price_min,
        "price_max": args.price_max,
        "sort": args.sort,
        "order": args.order,
    }
    query.update({key: value for key, value in optional.items() if value not in (None, "")})
    return query


def fetch_page(api_url, api_key, query):
    url = "%s?%s" % (api_url, urlencode(query))
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer %s" % api_key,
            "User-Agent": "ab-website-seo-optimization-drug-eg-sync/19.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return url, json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        if error.code == 401:
            raise SystemExit("Ready API rejected the bearer token. Details: %s" % detail) from error
        if error.code == 404:
            raise SystemExit("Ready API endpoint was not found. Check --api-url. Details: %s" % detail) from error
        if error.code == 429:
            raise SystemExit("Ready API rate limit exceeded. Stop now and resume after quota reset. Details: %s" % detail) from error
        raise


def extract_items(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "results", "drugs", "products", "all_products", "All_products"):
        values = payload.get(key)
        if isinstance(values, list):
            return values
    nested_products = []
    for key in ("ingredients", "active_ingredients", "all_data", "All Data"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for ingredient in values:
            if not isinstance(ingredient, dict):
                continue
            ingredient_name = first_present(ingredient, "name", "ingredient", "scientific_name", "active_ingredient")
            category = first_present(ingredient, "category", "therapeutic_category")
            for product_key in ("products", "items", "drugs"):
                products = ingredient.get(product_key)
                if not isinstance(products, list):
                    continue
                for product in products:
                    if isinstance(product, dict):
                        product = dict(product)
                        product.setdefault("scientific_name", ingredient_name)
                        product.setdefault("active_ingredient", ingredient_name)
                        product.setdefault("category", category)
                        nested_products.append(product)
        if nested_products:
            return nested_products
    return []


def first_present(data, *keys):
    for key in keys:
        value = data.get(key) if isinstance(data, dict) else None
        if value not in (None, False, "", []):
            return str(value)
    return False


def filter_signature(args):
    return {
        "api_url": args.api_url,
        "page_size": min(max(args.page_size, 1), 100),
        "search": args.search or "",
        "manufacturer": args.manufacturer or "",
        "route": args.route or "",
        "price_min": args.price_min,
        "price_max": args.price_max,
        "sort": args.sort or "",
        "order": args.order or "",
    }


def make_initial_state(args):
    return {
        "signature": filter_signature(args),
        "next_page": 1,
        "total_rows": 0,
        "request_count": 0,
        "done": False,
        "last_page": 0,
        "last_page_rows": 0,
    }


def load_state(env, args):
    parameter = env["ir.config_parameter"].sudo()
    if args.reset_state:
        parameter.set_param(args.state_key, "")
        return make_initial_state(args)
    raw_state = parameter.get_param(args.state_key)
    if not raw_state:
        return make_initial_state(args)
    try:
        state = json.loads(raw_state)
    except json.JSONDecodeError:
        return make_initial_state(args)
    if state.get("signature") != filter_signature(args):
        raise SystemExit(
            "Saved Drug-EG checkpoint uses different filters. "
            "Use the same arguments to resume, or pass --reset-state to start over."
        )
    return state


def save_state(env, args, state):
    env["ir.config_parameter"].sudo().set_param(args.state_key, json.dumps(state, sort_keys=True))


def print_state(state):
    print(json.dumps(state or {}, indent=2, sort_keys=True))


def payload_has_more(payload, item_count, page_size):
    if isinstance(payload, dict) and isinstance(payload.get("pagination"), dict):
        pagination = payload["pagination"]
        if "hasMore" in pagination:
            return bool(pagination.get("hasMore"))
        if "totalPages" in pagination and "page" in pagination:
            try:
                return int(pagination["page"]) < int(pagination["totalPages"])
            except (TypeError, ValueError):
                pass
    return item_count >= page_size


def main():
    args = parse_args()
    config.parse_config(["-c", args.config, "-d", args.database])
    odoo.service.server.load_server_wide_modules()
    registry = odoo.registry(args.database)
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        model = env["ab.product.drug.data"]
        state = load_state(env, args)
        if args.status:
            print_state(state)
            return
        if state.get("done"):
            print("Drug-EG import is already marked done. Use --reset-state to import again.")
            return
        total = int(state.get("total_rows") or 0)
        request_count = int(state.get("request_count") or 0)
        page = int(state.get("next_page") or 1)
        first_page_this_run = page
        print("Drug-EG import starting at page %s. Already processed rows: %s." % (page, total))
        try:
            while True:
                if args.max_pages and page >= first_page_this_run + args.max_pages:
                    print("Stopped after --max-pages=%s. Re-run the same command to continue." % args.max_pages)
                    break
                if args.max_requests and request_count >= args.max_requests:
                    print("Stopped at --max-requests=%s to protect API quota. Re-run after quota reset to continue." % args.max_requests)
                    break
                source_url, payload = fetch_page(args.api_url, args.api_key, build_query(args, page))
                request_count += 1
                items = extract_items(payload)
                if not items:
                    state.update({
                        "done": True,
                        "request_count": request_count,
                        "last_page": page,
                        "last_page_rows": 0,
                    })
                    save_state(env, args, state)
                    cr.commit()
                    break
                for item in items:
                    model.upsert_from_drug_eg_item(item, source_url=source_url)
                    total += 1
                state.update({
                    "next_page": page + 1,
                    "total_rows": total,
                    "request_count": request_count,
                    "done": not payload_has_more(payload, len(items), min(max(args.page_size, 1), 100)),
                    "last_page": page,
                    "last_page_rows": len(items),
                })
                save_state(env, args, state)
                cr.commit()
                print("Imported page %s: %s rows, total %s. Next page: %s" % (page, len(items), total, page + 1))
                if state["done"]:
                    break
                page += 1
                if args.request_delay and args.request_delay > 0:
                    time.sleep(args.request_delay)
        except KeyboardInterrupt:
            print("\nStopped by user. Last committed checkpoint:")
            print_state(state)
            return
        except SystemExit:
            raise
        except Exception:
            cr.rollback()
            print("Import stopped because of an error. Re-run the same command to continue from the last committed page.")
            raise
    print("Drug-EG import finished: %s rows processed across %s requests." % (total, request_count))


if __name__ == "__main__":
    main()
