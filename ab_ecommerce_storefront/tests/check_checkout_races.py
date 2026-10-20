import base64
import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from odoo import SUPERUSER_ID, api
from odoo.service.model import retrying


assert env.cr.dbname.startswith("ecom19_cart_hold_"), "Use an isolated reservation test database."
website = env.ref("website.default_website")
company = website.company_id
warehouse = env["stock.warehouse"].create({
    "name": "Concurrent cart validation", "code": secrets.token_hex(2).upper(),
    "company_id": company.id,
})
website.warehouse_id = warehouse
warehouse.out_type_id.reservation_method = "at_confirm"
partner = env["res.partner"].create({"name": "Concurrent cart validation"})
product = env["product.product"].create({
    "name": "Concurrent last unit", "type": "consu", "is_storable": True,
    "is_published": True, "company_id": company.id, "allow_out_of_stock_order": False,
    "list_price": 10,
})
env["stock.quant"].with_context(inventory_mode=True).create({
    "product_id": product.id, "location_id": warehouse.lot_stock_id.id,
    "inventory_quantity": 1,
}).action_apply_inventory()
carts = env["sale.order"].create([{
    "partner_id": partner.id, "website_id": website.id, "company_id": company.id,
    "warehouse_id": warehouse.id,
} for _ in range(2)])
submission = env["ab_storefront_submission"]._issue("prescription", website, "race-owner")
website_id, company_id, partner_id, product_id = website.id, company.id, partner.id, product.id
cart_ids, key = carts.ids, submission.key
env.cr.commit()


def concurrent(callback):
    barrier = Barrier(2)

    def worker(index):
        with env.registry.cursor() as cr:
            worker_env = api.Environment(cr, SUPERUSER_ID, {"allowed_company_ids": [company_id]})
            cr.execute("SELECT count(*) FROM sale_order WHERE id IN %s", (tuple(cart_ids),))
            barrier.wait(timeout=15)
            return retrying(lambda: callback(worker_env, index), worker_env)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(worker, range(2)))


results = concurrent(lambda worker_env, index: worker_env["sale.order"].browse(
    cart_ids[index]
)._cart_add(product_id, 1)["quantity"])
assert sorted(results) == [0, 1], results
env.invalidate_all()
held = env["ab_storefront_cart_hold"]._quantities(product, company, warehouse)
assert held[product_id] == 1, held
assert product.with_context(warehouse_id=warehouse.id).qty_available == 1
print("PASS: two concurrent carts allocate the last unit once; physical stock is unchanged", flush=True)
env.cr.commit()


def submit_prescription(worker_env, index):
    operation = worker_env["ab_storefront_submission"]._claim(
        key, "prescription", worker_env["website"].browse(website_id), "race-owner", {"image": "same-image"},
    )
    if not operation.prescription_id:
        prescription = worker_env["ab.prescription.order"].create({
            "partner_id": partner_id, "website_id": website_id, "company_id": company_id,
            "prescription_image": base64.b64encode(b"concurrent-validation"),
        })
        order = prescription._ab_storefront_create_sale_order(allow_unreviewed=True)
        operation.write({"prescription_id": prescription.id, "order_id": order.id})
    return operation.prescription_id.id, operation.order_id.id


results = concurrent(submit_prescription)
assert results[0] == results[1], results
print("PASS: concurrent retries return one prescription and one sale order", flush=True)

env.invalidate_all()
rx = submission.prescription_id
assert env["sale.order"].search_count([("origin", "=", rx.name)]) == 1
print("PASS: no orphan duplicate quotation remains after the concurrent retry", flush=True)
env.cr.rollback()
