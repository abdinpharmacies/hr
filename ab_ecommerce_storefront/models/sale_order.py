from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_amount, format_datetime, formatLang
from odoo.tools.urls import urljoin


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ab_prescription_order_ids = fields.One2many(
        "ab.prescription.order", "sale_order_id", string="Prescription Requests",
    )
    ab_call_center_order_type = fields.Selection(
        [
            ("normal", "Normal Order"),
            ("prescription", "Prescription Order"),
        ],
        string="Order Type",
        compute="_compute_ab_call_center_order_type",
        store=True,
        index=True,
    )
    ab_call_center_status = fields.Selection(
        [
            ("received", "Order Received"),
            ("confirmed", "Order Confirmed"),
            ("preparing", "Preparing Order"),
            ("warehouse_done", "Warehouse Dispatch Completed"),
            ("delivered", "Delivered"),
            ("cancelled", "Order Cancelled"),
            ("return_received", "Return Received"),
        ],
        string="Current Status",
        compute="_compute_ab_call_center_operational_fields",
        store=True,
        index=True,
    )
    ab_call_center_delivery_status = fields.Selection(
        [
            ("not_started", "Not Started"),
            ("waiting_stock", "Waiting for Stock"),
            ("preparing", "Ready for Preparation"),
            ("warehouse_done", "Warehouse Transfer Completed"),
            ("delivered", "Delivered"),
            ("partial", "Partially Processed"),
            ("cancelled", "Cancelled"),
        ],
        string="Delivery",
        compute="_compute_ab_call_center_operational_fields",
        store=True,
        index=True,
    )
    ab_call_center_payment_status = fields.Selection(
        [
            ("not_required", "Not Required"),
            ("cash_on_delivery", "Cash on Delivery"),
            ("paid", "Paid"),
            ("authorized", "Authorized"),
            ("pending", "Pending"),
            ("failed", "Failed"),
            ("unpaid", "Unpaid"),
        ],
        string="Payment",
        compute="_compute_ab_call_center_payment_status",
        store=True,
        index=True,
    )
    ab_call_center_workspace_data = fields.Json(
        compute="_compute_ab_call_center_workspace_data",
    )
    ab_last_mile_status = fields.Selection(
        [
            ("not_started", "Not Started"),
            ("out_for_delivery", "Out for Delivery"),
            ("delivered", "Delivered"),
        ],
        string="Last-mile Status",
        default="not_started",
        copy=False,
        tracking=True,
    )
    ab_last_mile_delivered_date = fields.Datetime(
        string="Delivered On",
        copy=False,
        readonly=True,
    )
    ab_last_mile_delivered_by_id = fields.Many2one(
        "res.users",
        string="Delivered By",
        copy=False,
        readonly=True,
    )

    @api.depends("ab_prescription_order_ids")
    def _compute_ab_call_center_order_type(self):
        for order in self:
            order.ab_call_center_order_type = (
                "prescription" if order.ab_prescription_order_ids else "normal"
            )

    def _ab_call_center_outgoing_pickings(self):
        self.ensure_one()
        return self.picking_ids.filtered(
            lambda picking: picking.picking_type_code == "outgoing"
            and picking.location_dest_id.usage == "customer"
            and picking.state != "cancel"
        )

    def _ab_call_center_return_moves(self):
        self.ensure_one()
        return self.picking_ids.move_ids.filtered(
            lambda move: move.state == "done"
            and move.origin_returned_move_id
            and move.location_id.usage == "customer"
            and move.location_dest_id.usage == "internal"
        )

    @api.depends(
        "state",
        "picking_ids.state",
        "picking_ids.picking_type_code",
        "picking_ids.location_dest_id.usage",
        "picking_ids.move_ids.state",
        "picking_ids.move_ids.origin_returned_move_id",
        "picking_ids.move_ids.location_id.usage",
        "picking_ids.move_ids.location_dest_id.usage",
        "ab_last_mile_status",
    )
    def _compute_ab_call_center_operational_fields(self):
        for order in self:
            if order.state == "cancel":
                order.ab_call_center_status = "cancelled"
                order.ab_call_center_delivery_status = "cancelled"
                continue

            outgoing = order._ab_call_center_outgoing_pickings()
            if order._ab_call_center_return_moves():
                order.ab_call_center_status = "return_received"
                order.ab_call_center_delivery_status = "warehouse_done"
            elif (
                order.ab_last_mile_status == "delivered"
                and outgoing
                and all(picking.state == "done" for picking in outgoing)
            ):
                order.ab_call_center_status = "delivered"
                order.ab_call_center_delivery_status = "delivered"
            elif not outgoing:
                order.ab_call_center_status = (
                    "confirmed" if order.state == "sale" else "received"
                )
                order.ab_call_center_delivery_status = "not_started"
            elif all(picking.state == "done" for picking in outgoing):
                order.ab_call_center_status = "warehouse_done"
                order.ab_call_center_delivery_status = "warehouse_done"
            elif any(picking.state == "done" for picking in outgoing):
                order.ab_call_center_status = "preparing"
                order.ab_call_center_delivery_status = "partial"
            elif any(picking.state == "assigned" for picking in outgoing):
                order.ab_call_center_status = "preparing"
                order.ab_call_center_delivery_status = "preparing"
            else:
                order.ab_call_center_status = "preparing"
                order.ab_call_center_delivery_status = "waiting_stock"

    def _ab_call_center_last_transaction(self):
        self.ensure_one()
        return self.sudo().transaction_ids._get_last()

    @api.depends(
        "amount_total",
        "currency_id",
        "transaction_ids",
        "transaction_ids.state",
        "transaction_ids.provider_id.custom_mode",
        "ab_prescription_order_ids.payment_method_id",
        "ab_prescription_order_ids.payment_method_id.code",
    )
    def _compute_ab_call_center_payment_status(self):
        for order in self:
            transaction = order._ab_call_center_last_transaction()
            prescription = order._ab_storefront_latest_prescription()
            prescription_method = prescription.payment_method_id if prescription else False
            if (
                not transaction
                and prescription_method
                and prescription_method.code == "cash_on_delivery"
            ):
                status = "cash_on_delivery"
            elif order.currency_id.is_zero(order.amount_total):
                status = "not_required"
            elif not transaction:
                status = "unpaid"
            elif (
                transaction.state in ("draft", "pending")
                and transaction.provider_id.custom_mode == "cash_on_delivery"
            ):
                status = "cash_on_delivery"
            elif transaction.state == "done":
                status = "paid"
            elif transaction.state == "authorized":
                status = "authorized"
            elif transaction.state in ("draft", "pending"):
                status = "pending"
            else:
                status = "failed"
            order.ab_call_center_payment_status = status

    def _ab_call_center_last_mile_state(self):
        self.ensure_one()
        if self.ab_last_mile_status in ("out_for_delivery", "delivered"):
            return self.ab_last_mile_status
        return False

    def action_ab_mark_delivered(self):
        self.check_access("write")
        if not self.env.user.has_group("sales_team.group_sale_manager"):
            raise AccessError(self.env._("Only Sales Administrators can mark orders as delivered."))

        delivered_at = fields.Datetime.now()
        for order in self:
            if order.state != "sale":
                raise UserError(self.env._("Only confirmed Sales Orders can be marked as delivered."))
            outgoing = order._ab_call_center_outgoing_pickings()
            if not outgoing:
                raise UserError(self.env._("Create the delivery operation before marking the order as delivered."))
            if not all(picking.state == "done" for picking in outgoing):
                raise UserError(self.env._("Validate the delivery operation before marking the order as delivered."))
            if order._ab_call_center_return_moves():
                raise UserError(self.env._("Returned orders cannot be marked as delivered."))

        self.write({
            "ab_last_mile_status": "delivered",
            "ab_last_mile_delivered_date": delivered_at,
            "ab_last_mile_delivered_by_id": self.env.user.id,
        })
        return True

    def _ab_call_center_status_label(self):
        self.ensure_one()
        labels = {
            "received": self.env._("Order received"),
            "confirmed": self.env._("Order confirmed"),
            "preparing": self.env._("Preparing order"),
            "warehouse_done": self.env._("Warehouse dispatch completed"),
            "delivered": self.env._("Delivered"),
            "cancelled": self.env._("Order cancelled"),
            "return_received": self.env._("Return received"),
        }
        return labels.get(self.ab_call_center_status, self.env._("Order received"))

    def _ab_call_center_delivery_label(self):
        self.ensure_one()
        labels = {
            "not_started": self.env._("Not started"),
            "waiting_stock": self.env._("Waiting for stock"),
            "preparing": self.env._("Ready for preparation"),
            "warehouse_done": self.env._("Warehouse transfer completed"),
            "delivered": self.env._("Delivered"),
            "partial": self.env._("Partially processed"),
            "cancelled": self.env._("Cancelled"),
        }
        return labels.get(self.ab_call_center_delivery_status, self.env._("Not started"))

    def _ab_call_center_payment_data(self):
        self.ensure_one()
        transaction = self._ab_call_center_last_transaction()
        transaction_sudo = transaction.sudo() if transaction else transaction
        labels = {
            "not_required": self.env._("No payment required"),
            "cash_on_delivery": self.env._("Cash on delivery"),
            "paid": self.env._("Paid"),
            "authorized": self.env._("Payment authorized"),
            "pending": self.env._("Payment pending"),
            "failed": self.env._("Payment failed"),
            "unpaid": self.env._("Unpaid"),
        }
        method = False
        if transaction_sudo:
            method = (
                transaction_sudo.payment_method_id.name
                or transaction_sudo.provider_id.name
            )
        else:
            prescription = self._ab_storefront_latest_prescription()
            if prescription:
                method = prescription.payment_method_id.name
        if not method and self.preferred_payment_method_line_id:
            method = self.preferred_payment_method_line_id.name
        return {
            "status": self.ab_call_center_payment_status,
            "label": labels.get(self.ab_call_center_payment_status, self.env._("Unpaid")),
            "method": method or self.env._("Not specified"),
            "reference": transaction_sudo.reference if transaction_sudo else False,
        }

    def _ab_call_center_primary_picking(self):
        self.ensure_one()
        outgoing = self._ab_call_center_outgoing_pickings()
        active = outgoing.filtered(lambda picking: picking.state != "done")
        return (active or outgoing).sorted("id", reverse=True)[:1]

    def _ab_storefront_prescription_tracking_steps(self, prescription):
        self.ensure_one()
        outgoing = self._ab_call_center_outgoing_pickings()
        warehouse_done = bool(outgoing) and all(picking.state == "done" for picking in outgoing)
        preparation_started = bool(outgoing)
        last_mile_state = self._ab_call_center_last_mile_state()
        stage_keys = [
            "new",
            "under_review",
            "waiting_call_center",
            "confirmed",
            "preparing",
            "out_for_delivery",
            "delivered",
        ]
        if last_mile_state == "delivered" or prescription.state == "delivered":
            current_key = "delivered"
        elif last_mile_state == "out_for_delivery" or warehouse_done or prescription.state == "out_for_delivery":
            current_key = "out_for_delivery"
        elif preparation_started or prescription.state == "preparing":
            current_key = "preparing"
        elif self.state == "sale" or prescription.state == "confirmed":
            current_key = "confirmed"
        elif prescription.state in stage_keys[:3]:
            current_key = prescription.state
        else:
            current_key = "new"
        current_index = stage_keys.index(current_key)

        steps = []
        delivered = current_key == "delivered"
        for index, key in enumerate(stage_keys):
            label, description = prescription._STATE_COPY[key]
            if delivered:
                state = "complete"
            elif index < current_index:
                state = "complete"
            elif index == current_index:
                state = "current"
            else:
                state = "pending"
            steps.append({
                "key": "prescription_" + key if index < 3 else key,
                "label": self.env._(label),
                "description": self.env._(description),
                "state": state,
            })
        return steps

    def _ab_call_center_timeline(self):
        self.ensure_one()
        prescription = self._ab_storefront_latest_prescription()
        picking = self._ab_call_center_primary_picking()
        outgoing = self._ab_call_center_outgoing_pickings()
        warehouse_done = bool(outgoing) and all(
            current.state == "done" for current in outgoing
        )
        preparation_started = bool(outgoing)
        confirmed = self.state == "sale"
        last_mile_state = self._ab_call_center_last_mile_state()

        if confirmed:
            received_state = "complete"
            confirmed_state = "complete" if preparation_started else "current"
        else:
            received_state = "current"
            confirmed_state = "upcoming"
        preparing_state = "upcoming"
        if preparation_started:
            preparing_state = "complete" if warehouse_done else "current"

        out_for_delivery_state = "upcoming"
        delivered_state = "upcoming"
        if last_mile_state == "out_for_delivery":
            out_for_delivery_state = "current"
        elif last_mile_state == "delivered":
            out_for_delivery_state = "complete"
            delivered_state = "complete"

        availability = picking.products_availability if picking else False
        picking_reference = picking.name if picking else False
        preparation_detail = self.env._("Waiting for a delivery operation.")
        if picking:
            preparation_detail = self.env._(
                "Delivery %(delivery)s — %(availability)s",
                delivery=picking.name,
                availability=availability or self._ab_call_center_delivery_label(),
            )

        if prescription:
            return (
                self._ab_storefront_prescription_tracking_steps(prescription),
                picking_reference,
                availability,
                warehouse_done and not last_mile_state,
            )

        return [
            {
                "key": "received",
                "label": self.env._("Order received"),
                "description": self.env._("The customer request is recorded in Odoo."),
                "detail": format_datetime(self.env, self.create_date, dt_format=False)
                if self.create_date else False,
                "operation": self.env._(
                    "Payment method assigned automatically: %(method)s",
                    method=prescription.payment_method_id.name,
                ) if prescription and prescription.payment_method_id else False,
                "state": received_state,
            },
            {
                "key": "confirmed",
                "label": self.env._("Order confirmed"),
                "description": self.env._("The Sales Order is confirmed."),
                "detail": format_datetime(self.env, self.date_order, dt_format=False)
                if confirmed and self.date_order else False,
                "state": confirmed_state,
            },
            {
                "key": "preparing",
                "label": self.env._("Preparing order"),
                "description": self.env._("Products move through the native warehouse operation."),
                "detail": preparation_detail,
                "state": preparing_state,
                "delivery_id": picking.id if picking else False,
            },
            {
                "key": "out_for_delivery",
                "label": self.env._("Out for delivery"),
                "description": self.env._("Courier handoff has not been recorded by an authoritative state."),
                "detail": self.env._("Last-mile status is not configured") if warehouse_done else False,
                "state": out_for_delivery_state,
                "gap": warehouse_done and not last_mile_state,
            },
            {
                "key": "delivered",
                "label": self.env._("Delivered"),
                "description": self.env._("Customer receipt requires a reliable delivery confirmation."),
                "detail": False,
                "state": delivered_state,
            },
        ], picking_reference, availability, warehouse_done and not last_mile_state

    def _ab_call_center_attention_items(self, last_mile_gap):
        self.ensure_one()
        items = []
        payment = self.ab_call_center_payment_status
        if payment == "failed":
            items.append({"level": "danger", "label": self.env._("Payment failed and needs follow-up.")})
        elif payment in ("pending", "authorized"):
            items.append({"level": "warning", "label": self.env._("Payment confirmation is pending.")})
        elif payment == "unpaid" and self.state in ("sent", "sale"):
            items.append({"level": "warning", "label": self.env._("No successful payment is recorded.")})

        shipping = self.partner_shipping_id
        if not shipping or not (shipping.street or shipping.city or shipping.state_id or shipping.country_id):
            items.append({"level": "warning", "label": self.env._("Delivery address is incomplete.")})

        picking = self._ab_call_center_primary_picking()
        if picking and picking.products_availability_state == "late":
            items.append({"level": "danger", "label": self.env._("Product availability needs review.")})
        if last_mile_gap:
            items.append({
                "level": "info",
                "label": self.env._("Warehouse processing is complete, but courier handoff is not recorded."),
            })
        return items

    def _ab_call_center_next_action(self, last_mile_gap):
        self.ensure_one()
        prescription = self._ab_storefront_latest_prescription()
        picking = self._ab_call_center_primary_picking()
        if self.state == "cancel":
            return self.env._("Review the cancellation and any required customer follow-up.")
        if self.ab_call_center_payment_status == "failed":
            return self.env._("Contact the customer or retry payment using the native payment flow.")
        if self.state in ("draft", "sent"):
            if prescription:
                return self.env._("Review the prescription and complete the order before confirmation.")
            return self.env._("Verify customer and order details, then confirm the Sales Order.")
        if not picking:
            return self.env._("Wait for the native Delivery Order to be created.")
        if picking.products_availability_state == "late":
            return self.env._("Review product availability with the warehouse team.")
        if picking.state == "assigned":
            return self.env._("The warehouse can prepare the reserved products.")
        if picking.state in ("draft", "waiting", "confirmed"):
            return self.env._("Follow up product reservation with the warehouse team.")
        if last_mile_gap:
            return self.env._("Record courier handoff in an authoritative last-mile workflow.")
        return self.env._("Continue monitoring the native delivery operation.")

    @api.depends(
        "name",
        "state",
        "create_date",
        "date_order",
        "amount_total",
        "currency_id",
        "partner_id.name",
        "partner_id.phone",
        "partner_id.email",
        "partner_shipping_id.contact_address_inline",
        "user_id.name",
        "ab_call_center_order_type",
        "ab_call_center_status",
        "ab_call_center_delivery_status",
        "ab_call_center_payment_status",
        "ab_last_mile_status",
        "ab_last_mile_delivered_date",
        "ab_last_mile_delivered_by_id",
        "ab_prescription_order_ids.name",
        "ab_prescription_order_ids.state",
        "ab_prescription_order_ids.payment_method_id",
        "picking_ids.state",
        "picking_ids.name",
        "picking_ids.products_availability",
        "picking_ids.products_availability_state",
        "transaction_ids.state",
        "transaction_ids.reference",
        "transaction_ids.payment_method_id",
        "transaction_ids.provider_id",
    )
    def _compute_ab_call_center_workspace_data(self):
        can_read_delivery = self.env["stock.picking"].has_access("read")
        type_labels = {
            "normal": self.env._("Normal order"),
            "prescription": self.env._("Prescription order"),
        }
        for order in self:
            timeline, picking_reference, availability, last_mile_gap = (
                order._ab_call_center_timeline()
            )
            prescription = order._ab_storefront_latest_prescription()
            shipping = order.partner_shipping_id
            mobile = (
                order.partner_id.mobile
                if "mobile" in order.partner_id._fields
                else False
            )
            phone = order.partner_id.phone or mobile
            order.ab_call_center_workspace_data = {
                "order_id": order.id,
                "name": order.name,
                "customer": {
                    "name": order.partner_id.name or order.env._("Not specified"),
                    "phone": phone or False,
                    "email": order.partner_id.email or False,
                    "address": shipping.contact_address_inline if shipping else False,
                },
                "order_type": {
                    "value": order.ab_call_center_order_type,
                    "label": type_labels.get(order.ab_call_center_order_type),
                },
                "status": {
                    "value": order.ab_call_center_status,
                    "label": order._ab_call_center_status_label(),
                },
                "payment": order._ab_call_center_payment_data(),
                "delivery": {
                    "count": order.delivery_count,
                    "can_read": can_read_delivery,
                    "label": order._ab_call_center_delivery_label(),
                    "reference": picking_reference,
                    "availability": availability,
                    "last_mile_gap": last_mile_gap,
                },
                "total": format_amount(order.env, order.amount_total, order.currency_id),
                "responsible": order.user_id.name or order.env._("Order Support Team"),
                "timeline": timeline,
                "attention": order._ab_call_center_attention_items(last_mile_gap),
                "next_action": order._ab_call_center_next_action(last_mile_gap),
                "prescription": {
                    "id": prescription.id,
                    "name": prescription.name,
                    "state": prescription.state_label,
                    "image_url": (
                        f"/web/image/ab.prescription.order/{prescription.id}/prescription_image"
                    ),
                } if prescription else False,
            }

    def get_ab_call_center_delivery_summary(self):
        self.ensure_one()
        self.check_access("read")
        pickings = self._ab_call_center_outgoing_pickings().sorted("id", reverse=True)
        pickings.check_access("read")
        summaries = []
        state_labels = {
            "draft": self.env._("Draft"),
            "waiting": self.env._("Waiting for another operation"),
            "confirmed": self.env._("Waiting for stock"),
            "assigned": self.env._("Ready"),
            "done": self.env._("Warehouse transfer completed"),
            "cancel": self.env._("Cancelled"),
        }
        for picking in pickings:
            moves = picking.move_ids.filtered(
                lambda move: move.state != "cancel" and move.product_id
            )
            moves.check_access("read")
            products = []
            for move in moves:
                quantity = move.quantity if move.state == "done" else move.product_uom_qty
                products.append({
                    "id": move.id,
                    "product_id": move.product_id.id,
                    "name": move.product_id.display_name,
                    "quantity": formatLang(self.env, quantity),
                    "uom": move.product_uom.name,
                    "image_url": f"/web/image/product.product/{move.product_id.id}/image_128",
                })
            summaries.append({
                "id": picking.id,
                "name": picking.name,
                "source": picking.origin or self.name,
                "address": picking.partner_id.contact_address_inline or False,
                "status": state_labels.get(picking.state, picking.display_name),
                "status_value": picking.state,
                "availability": picking.products_availability or self.env._("Not available"),
                "availability_state": picking.products_availability_state or False,
                "scheduled_date": format_datetime(
                    self.env, picking.scheduled_date, dt_format=False,
                ) if picking.scheduled_date else False,
                "products": products,
            })
        return summaries

    def _cart_add(self, product_id, quantity=1.0, *, uom_id=None, **kwargs):
        result = super()._cart_add(product_id, quantity=quantity, uom_id=uom_id, **kwargs)
        if quantity > 0 and self.partner_id and not self.env.user._is_public():
            self.partner_id.sudo().write({"ab_storefront_has_cart_history": True})
        return result

    def _ab_storefront_latest_prescription(self):
        self.ensure_one()
        return self.ab_prescription_order_ids.filtered(
            lambda prescription: prescription.partner_id.commercial_partner_id
            == self.partner_id.commercial_partner_id
            and prescription.company_id == self.company_id
        ).sorted("id", reverse=True)[:1]

    @api.constrains("partner_id", "company_id", "website_id")
    def _check_prescription_customer(self):
        self.ab_prescription_order_ids._check_sale_order_customer()

    def _ab_storefront_payment_label(self):
        self.ensure_one()
        tx = self.get_portal_last_transaction()
        if tx:
            if tx.state in ("draft", "pending") and tx.provider_id.custom_mode == "cash_on_delivery":
                return self.env._("Cash on delivery")
            labels = {
                "draft": self.env._("Payment initiated"),
                "pending": self.env._("Payment processing"),
                "authorized": self.env._("Payment authorized"),
                "done": self.env._("Payment successful"),
                "cancel": self.env._("Payment cancelled"),
                "error": self.env._("Payment failed"),
            }
            return labels.get(tx.state, self.env._("Payment pending"))
        prescription = self._ab_storefront_latest_prescription()
        if (
            prescription
            and prescription.payment_method_id.code == "cash_on_delivery"
        ):
            return self.env._("Cash on delivery")
        if self.currency_id.is_zero(self.amount_total):
            return self.env._("No payment required")
        return self.env._("Payment pending")

    def _ab_storefront_delivery_stage(self):
        self.ensure_one()
        if self.state == "cancel":
            return "cancelled"
        stage = "confirmed" if self.state == "sale" else "created"
        if "picking_ids" not in self._fields:
            return stage
        # Warehouse completion proves dispatch, not receipt by the customer.
        outgoing = self.picking_ids.filtered(
            lambda picking: picking.picking_type_code == "outgoing"
            and picking.location_dest_id.usage == "customer" and picking.state != "cancel"
        )
        returns = self.picking_ids.move_ids.filtered(
            lambda move: move.state == "done" and move.origin_returned_move_id
            and move.location_id.usage == "customer"
            and move.location_dest_id.usage == "internal"
        )
        if returns:
            return "return_received"
        if self._ab_call_center_last_mile_state() == "delivered":
            return "delivered"
        if outgoing and all(picking.state == "done" for picking in outgoing):
            return "shipped"
        if any(picking.state == "done" for picking in outgoing):
            return "partially_shipped"
        if any(picking.state == "assigned" for picking in outgoing):
            return "preparing"
        return stage

    def _ab_storefront_tracking_steps(self, include_prescription=True):
        self.ensure_one()
        prescription = self._ab_storefront_latest_prescription() if include_prescription else False
        if prescription:
            return self._ab_storefront_prescription_tracking_steps(prescription)
        steps = prescription._ab_storefront_tracking_steps(include_order=False) if prescription else []
        stage = self._ab_storefront_delivery_stage()
        definitions = [
            ("created", self.env._("Order created"), self.env._("We received your order details. We will contact you soon.")),
            ("confirmed", self.env._("Order confirmed"), self.env._("The order is confirmed by Abdin Pharmacies.")),
            ("preparing", self.env._("Preparing order"), self.env._("Your items are reserved for preparation.")),
            ("shipped", self.env._("Out for delivery"), self.env._("Your order has left the pharmacy and is on the way.")),
            ("delivered", self.env._("Delivered"), self.env._("Your order has been delivered.")),
        ]
        keys = [key for key, label, description in definitions]
        current = keys.index(stage) if stage in keys else (2 if stage == "partially_shipped" else 0)
        for index, (key, label, description) in enumerate(definitions):
            if prescription and key == "created":
                continue
            if stage in ("cancelled", "return_received") and index > 0:
                continue
            complete = (
                index < current
                or stage in ("cancelled", "return_received")
                or (stage == "delivered" and index <= current)
            )
            steps.append({
                "key": key, "label": label, "description": description,
                "state": "complete" if complete
                else ("current" if index == current else "pending"),
            })
        if prescription and self.state in ("draft", "sent"):
            for step in steps:
                if step["key"] in keys:
                    step["state"] = "pending"
            if prescription.state in ("cancelled", "rejected"):
                steps = [step for step in steps if step["state"] != "pending"]
        if stage == "partially_shipped":
            for shipped_index, step in enumerate(steps):
                if step["key"] == "shipped":
                    break
            else:
                shipped_index = len(steps)
            steps.insert(shipped_index, {
                "key": stage, "label": self.env._("Partially shipped"),
                "description": self.env._("Some items have been dispatched; others are still being prepared."),
                "state": "current",
            })
            for step in steps:
                if step["key"] == "preparing":
                    step["state"] = "complete"
        exceptions = {
            "cancelled": (self.env._("Order cancelled"), self.env._("This order was cancelled.")),
            "return_received": (self.env._("Return received"), self.env._("Returned items were received by the warehouse.")),
        }
        if stage in exceptions:
            steps = [dict(step, state="complete") for step in steps if step["state"] != "pending"]
            label, description = exceptions[stage]
            steps.append({"key": stage, "label": label, "description": description, "state": "exception"})
        elif self.get_portal_last_transaction().state in ("error", "cancel"):
            steps = [step for step in steps if step["state"] != "pending"]
            steps.append({
                "key": "payment_failed", "label": self.env._("Payment failed"),
                "description": self.env._("The payment could not be completed."),
                "state": "exception",
            })
        return steps

    def _ab_storefront_customer_invoices(self):
        self.ensure_one()
        return self.invoice_ids.filtered(
            lambda invoice: invoice.state == "posted"
            and invoice.move_type in ("out_invoice", "out_refund")
            and invoice.company_id == self.company_id
            and invoice.commercial_partner_id == self.partner_invoice_id.commercial_partner_id
        ).sorted("invoice_date", reverse=True)

    def _ab_storefront_report_terms_url(self):
        self.ensure_one()
        use_invoice_terms = self.env["ir.config_parameter"].sudo().get_param(
            "account.use_invoice_terms",
        )
        if not use_invoice_terms or self.company_id.terms_type != "html":
            return False
        return urljoin(self.get_base_url(), "/terms")

    def _ab_storefront_report_discount_amount(self):
        self.ensure_one()
        discount = 0.0
        for line in self.order_line:
            if line.display_type or not line.discount:
                continue
            if "is_delivery" in line._fields and line.is_delivery:
                continue
            discount += line.price_unit * line.product_uom_qty * line.discount / 100.0
        return self.currency_id.round(discount)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    ab_stock_qty_available = fields.Float(
        string="On Hand",
        compute="_compute_ab_stock_snapshot",
        digits="Product Unit of Measure",
    )
    ab_stock_incoming_qty = fields.Float(
        string="Incoming",
        compute="_compute_ab_stock_snapshot",
        digits="Product Unit of Measure",
    )
    ab_stock_outgoing_qty = fields.Float(
        string="Outgoing",
        compute="_compute_ab_stock_snapshot",
        digits="Product Unit of Measure",
    )
    ab_stock_forecasted_qty = fields.Float(
        string="Forecasted",
        compute="_compute_ab_stock_snapshot",
        digits="Product Unit of Measure",
    )

    @api.depends("product_id", "order_id.warehouse_id")
    def _compute_ab_stock_snapshot(self):
        for line in self:
            product = line.product_id
            if not product:
                line.ab_stock_qty_available = 0.0
                line.ab_stock_incoming_qty = 0.0
                line.ab_stock_outgoing_qty = 0.0
                line.ab_stock_forecasted_qty = 0.0
                continue

            if line.order_id.warehouse_id:
                product = product.with_context(warehouse=line.order_id.warehouse_id.id)

            line.ab_stock_qty_available = product.qty_available
            line.ab_stock_incoming_qty = product.incoming_qty
            line.ab_stock_outgoing_qty = product.outgoing_qty
            line.ab_stock_forecasted_qty = product.virtual_available

    def _ab_storefront_report_line_parts(self):
        self.ensure_one()
        raw_lines = [
            value.strip()
            for value in (self.name or "").splitlines()
            if value and value.strip()
        ]
        product = self.product_id
        sku = product.default_code or ""
        if "is_delivery" in self._fields and self.is_delivery:
            return {
                "sku": "",
                "name": raw_lines[0] if raw_lines else product.display_name,
                "description": "\n".join(raw_lines[1:]),
            }

        fallback_name = product.with_context(display_default_code=False).display_name
        product_name = raw_lines[0] if raw_lines else fallback_name
        if sku and product_name.startswith(f"[{sku}]"):
            product_name = product_name[len(sku) + 2:].strip()
        description_lines = raw_lines[1:]

        comparable_names = {
            value.strip()
            for value in (
                fallback_name,
                product.name,
                product.product_tmpl_id.name,
            )
            if value and value.strip()
        }
        if product_name in comparable_names:
            description = "\n".join(description_lines)
        else:
            description = "\n".join(description_lines)
        return {
            "sku": sku,
            "name": product_name or fallback_name,
            "description": description,
        }

    def _ab_storefront_report_tax_label(self):
        self.ensure_one()
        labels = [
            tax.tax_label or tax.name
            for tax in self.tax_ids
            if tax.tax_label or tax.name
        ]
        return ", ".join(labels)
