def obj(**properties):
    return {"type": "object", "properties": properties}


def ref(name):
    return {"$ref": "#/components/schemas/" + name}


def array(item):
    return {"type": "array", "items": item}


def paged(item):
    return obj(items=array(item), page=INTEGER, limit=INTEGER, has_more=BOOLEAN)


STRING = {"type": "string"}
INTEGER = {"type": "integer"}
NUMBER = {"type": "number"}
BOOLEAN = {"type": "boolean"}
NULLABLE_ID = {"type": "integer", "nullable": True}
DATE = {"type": "string", "format": "date-time", "nullable": True}

SCHEMAS = {
    "Product": obj(id=INTEGER, name=STRING, description=STRING, price=NUMBER,
                   original_price={"type": "number", "nullable": True}, currency=STRING,
                   image_url=STRING, variant_ids=array(INTEGER), category_ids=array(INTEGER)),
    "Variant": obj(id=INTEGER, name=STRING, price=NUMBER,
                   available_quantity={"type": "number", "nullable": True}, attributes=array(STRING)),
    "Address": obj(id=INTEGER, name=STRING, phone=STRING, street=STRING, street2=STRING,
                   city=STRING, zip=STRING, country_id=NULLABLE_ID, state_id=NULLABLE_ID),
    "Profile": obj(id=INTEGER, name=STRING, email=STRING, phone=STRING, avatar=STRING),
    "OrderLine": obj(id=INTEGER, product_id=INTEGER, name=STRING, quantity=NUMBER,
                     unit_price=NUMBER, discount=NUMBER, subtotal=NUMBER, total=NUMBER,
                     is_delivery=BOOLEAN, is_reward=BOOLEAN),
    "Order": obj(id=NULLABLE_ID, reference=STRING, state=STRING, currency=STRING,
                 untaxed=NUMBER, tax=NUMBER, total=NUMBER, shipping_address_id=INTEGER,
                 delivery_method_id=NULLABLE_ID, hold_expires_at=DATE, lines=array(ref("OrderLine"))),
    "TrackingStep": obj(key=STRING, label=STRING, description=STRING, state=STRING),
    "Tokens": obj(access_token=STRING, refresh_token=STRING, token_type=STRING,
                  expires_in=INTEGER, refresh_expires_in=INTEGER,
                  user=obj(id=INTEGER, name=STRING)),
    "DeviceChallenge": obj(verification_required=BOOLEAN, challenge_token=STRING, browser_token=STRING),
    "DeviceSession": obj(id=STRING, device_name=STRING, current=BOOLEAN,
                         created_at=DATE, last_used_at=DATE, last_refreshed_at=DATE,
                         refresh_expires_at=DATE),
    "Prescription": obj(id=INTEGER, reference=STRING, state=STRING, state_label=STRING,
                        customer_note=STRING, created_at=DATE, order_id=NULLABLE_ID, image_url=STRING),
    "Category": obj(id=INTEGER, name=STRING, parent_id=NULLABLE_ID),
    "Brand": obj(id=INTEGER, name=STRING, product_count=INTEGER),
    "Branch": obj(id=STRING, name=STRING, address=STRING, region=STRING, latitude=NUMBER, longitude=NUMBER),
    "Invoice": obj(id=INTEGER, number=STRING, date={"type": "string", "format": "date", "nullable": True},
                   total=NUMBER, currency=STRING, payment_state=STRING, download_url=STRING),
}
SCHEMAS["Tokens"]["required"] = ["access_token", "refresh_token", "token_type", "expires_in", "refresh_expires_in"]
SCHEMAS["DeviceChallenge"]["required"] = ["verification_required"]

RESULTS = {
    "browser_start": obj(flow_token=STRING, authorization_url=STRING, expires_in=INTEGER, poll_interval=INTEGER),
    "browser_token": {"oneOf": [ref("Tokens"), dict(obj(authorization_pending=BOOLEAN), required=["authorization_pending"])]},
    "login": {"oneOf": [ref("Tokens"), ref("DeviceChallenge")]},
    "verify_device": {"oneOf": [ref("Tokens"), ref("DeviceChallenge")]},
    "register": ref("Tokens"), "phone_complete": ref("Tokens"), "refresh": ref("Tokens"),
    "logout": obj(revoked=BOOLEAN), "sessions": array(ref("DeviceSession")),
    "revoke_session": obj(revoked=BOOLEAN), "logout_all": obj(revoked=INTEGER),
    "phone_start": obj(challenge_token=STRING, browser_token=STRING, verification_url=STRING),
    "recovery": obj(accepted=BOOLEAN, challenge_token=STRING, browser_token=STRING),
    "recovery_verify": obj(verified=BOOLEAN, grant_token={"type": "string", "nullable": True}),
    "recovery_reset": obj(reset=BOOLEAN), "email_confirm": obj(verified=BOOLEAN),
    "config": obj(name=STRING, currency=STRING, languages=array(STRING), version=STRING,
                  authentication=STRING, guest_browsing=BOOLEAN, checkout_requires_login=BOOLEAN,
                  signup_url=STRING, account_security_url=STRING, google_login_url=STRING),
    "products": paged(ref("Product")), "offers": paged(ref("Product")),
    "product": {"allOf": [ref("Product"), obj(description_html=STRING, variants=array(ref("Variant")))]},
    "categories": array(ref("Category")), "brands": array(ref("Brand")),
    "home": obj(best_sellers=array(ref("Product")), offers=array(ref("Product")), categories=array(ref("Category")),
                banners=array(obj(id=INTEGER, title=STRING, subtitle=STRING, image_url=STRING, link=STRING, button_text=STRING))),
    "me": ref("Profile"), "update_me": obj(updated=BOOLEAN),
    "addresses": array(ref("Address")), "add_address": ref("Address"), "update_address": ref("Address"),
    "countries": array(obj(id=INTEGER, name=STRING, code=STRING)), "states": array(obj(id=INTEGER, name=STRING)),
    "cart": ref("Order"), "add_cart_item": ref("Order"), "update_cart_item": ref("Order"),
    "cart_address": ref("Order"), "set_delivery": ref("Order"), "coupon": ref("Order"),
    "rewards": array(obj(coupon_id=INTEGER, reward_id=INTEGER, description=STRING, product_ids=array(INTEGER))),
    "claim_reward": ref("Order"),
    "delivery_methods": array(obj(id=INTEGER, name=STRING, price=NUMBER, currency=STRING)),
    "orders": paged(ref("Order")),
    "order": {"allOf": [ref("Order"), obj(tracking=array(ref("TrackingStep")), payment_state={"type": "string", "nullable": True})]},
    "wishlist": paged(ref("Product")), "add_wishlist": obj(added=BOOLEAN), "remove_wishlist": obj(removed=BOOLEAN),
    "history": array(ref("Product")), "record_history": obj(recorded=BOOLEAN), "clear_history": obj(cleared=BOOLEAN),
    "contact": obj(submitted=BOOLEAN), "branches": array(ref("Branch")),
    "pages": obj(about=STRING, terms=STRING, returns=STRING, partnerships=STRING, contact=STRING),
    "payment_methods": array(obj(provider_id=INTEGER, name=STRING, code=STRING, test_mode=BOOLEAN,
                                  methods=array(obj(id=INTEGER, name=STRING, code=STRING)))),
    "prepare_checkout": obj(order=ref("Order"), idempotency_key=STRING),
    "payment": obj(order_id=INTEGER, processing={"type": "object", "additionalProperties": True}),
    "invoices": array(ref("Invoice")), "prescription_submission": obj(idempotency_key=STRING, expires_at=DATE),
    "upload_prescription": ref("Prescription"), "prescriptions": paged(ref("Prescription")),
    "prescription": ref("Prescription"),
}
