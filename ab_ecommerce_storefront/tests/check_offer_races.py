import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from odoo import Command, SUPERUSER_ID, api
from odoo.exceptions import ValidationError
from odoo.service.model import retrying


assert env.cr.dbname.startswith("codex_offer_once_"), "Use an isolated offer test database."
website = env.ref("website.default_website")
company = website.company_id
partner = env["res.partner"].create({"name": "Concurrent offer customer"})
pricelist = env["product.pricelist"].create({
    "name": "Concurrent offer prices", "website_id": website.id,
    "company_id": company.id, "currency_id": company.currency_id.id,
})

for offer_type in ("price", "gift"):
    product = env["product.product"].create({
        "name": "Concurrent offer " + secrets.token_hex(4), "type": "consu",
        "list_price": 100, "taxes_id": [Command.clear()], "company_id": company.id,
    })
    offer = env["ab_storefront_offer"].create({
        "name": "Concurrent " + offer_type, "website_id": website.id,
        "product_id": product.id, "offer_type": offer_type, "pricelist_id": pricelist.id,
        "price_before": 100, "price_after": 80, "once_per_customer": True,
        "buy_qty": 2, "gift_qty": 1,
    })
    orders = env["sale.order"].create([{
        "partner_id": partner.id, "website_id": website.id,
        "company_id": company.id, "pricelist_id": pricelist.id,
        "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 2})],
    } for unused in range(2)])
    for order in orders:
        order._update_programs_and_rewards()
        order._auto_apply_rewards()
    order_ids = orders.ids
    company_id = company.id
    env.cr.commit()
    barrier = Barrier(2)

    def confirm(order_id):
        with env.registry.cursor() as cr:
            worker_env = api.Environment(cr, SUPERUSER_ID, {"allowed_company_ids": [company_id]})
            order = worker_env["sale.order"].browse(order_id)
            order._ab_check_offer_eligibility()
            barrier.wait(timeout=30)
            try:
                retrying(order.action_confirm, worker_env)
                return "confirmed"
            except ValidationError:
                cr.rollback()
                return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, order_ids))
    assert sorted(results) == ["blocked", "confirmed"], results
    env.invalidate_all()
    assert len(orders.filtered(lambda order: order.state == "sale")) == 1
    assert env["ab_storefront_offer_use"].search_count([("offer_id", "=", offer.id)]) == 1
    print(f"PASS: simultaneous {offer_type} confirmations produce one confirmed order and one usage record", flush=True)
    env.cr.commit()
