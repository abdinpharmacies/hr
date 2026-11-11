from odoo import api, models


class AbSalesUiApi(models.TransientModel):
    _name = "ab_sales_ui_api"
    _inherit = ["ab_sales_ui_api", "ab_sales_prevent.access.mixin"]

    @api.model
    def _blocked_super(self, method_name, *args, **kwargs):
        self._raise_sales_prevented()
        return getattr(super(AbSalesUiApi, self), method_name)(*args, **kwargs)

    @api.model
    def get_printer_settings(self):
        return self._blocked_super("get_printer_settings")

    @api.model
    def set_printer_settings(self, printer_name=None, receipt_header=None, receipt_footer=None):
        return self._blocked_super(
            "set_printer_settings",
            printer_name=printer_name,
            receipt_header=receipt_header,
            receipt_footer=receipt_footer,
        )

    @api.model
    def bill_wizard_discover_shared_printers(self, start_ip="", end_ip=""):
        return self._blocked_super(
            "bill_wizard_discover_shared_printers",
            start_ip=start_ip,
            end_ip=end_ip,
        )

    @api.model
    def bill_wizard_get_print_options(self):
        return self._blocked_super("bill_wizard_get_print_options")

    @api.model
    def bill_wizard_set_print_preferences(self, printer_name="", print_format="a4", printer_id=0):
        return self._blocked_super(
            "bill_wizard_set_print_preferences",
            printer_name=printer_name,
            print_format=print_format,
            printer_id=printer_id,
        )

    @api.model
    def get_pos_ui_settings(self):
        return self._blocked_super("get_pos_ui_settings")

    @api.model
    def save_pos_ui_settings(self, settings=None):
        return self._blocked_super("save_pos_ui_settings", settings=settings)

    @api.model
    def get_sales_store_settings(self):
        return self._blocked_super("get_sales_store_settings")

    @api.model
    def get_products_promo_status(self, product_ids, store_id=None):
        return self._blocked_super(
            "get_products_promo_status",
            product_ids,
            store_id=store_id,
        )

    @api.model
    def search_products(self, *args, **kwargs):
        return self._blocked_super("search_products", *args, **kwargs)

    @api.model
    def pos_customer_insights(self, header_id=None, store_id=None, customer_phone=None, customer_name=None):
        return self._blocked_super(
            "pos_customer_insights",
            header_id=header_id,
            store_id=store_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
        )

    @api.model
    def pos_customer_invoices(self, header_id=None, store_id=None, customer_phone=None, limit=20):
        return self._blocked_super(
            "pos_customer_invoices",
            header_id=header_id,
            store_id=store_id,
            customer_phone=customer_phone,
            limit=limit,
        )

    @api.model
    def apply_products(self, header_id, items):
        return self._blocked_super("apply_products", header_id, items)

    @api.model
    def pos_store_status(self, store_id=None):
        return self._blocked_super("pos_store_status", store_id=store_id)

    @api.model
    def pos_replication_active_crons(self):
        return self._blocked_super("pos_replication_active_crons")

    @api.model
    def pos_replication_run_cron(self, cron_id):
        return self._blocked_super("pos_replication_run_cron", cron_id)

    @api.model
    def bill_wizard_render_print_text_from_payload(self, payload=None, print_format="a4"):
        return self._blocked_super(
            "bill_wizard_render_print_text_from_payload",
            payload=payload,
            print_format=print_format,
        )

    @api.model
    def bill_wizard_render_print_html_from_payload(self, payload=None, print_format="a4"):
        return self._blocked_super(
            "bill_wizard_render_print_html_from_payload",
            payload=payload,
            print_format=print_format,
        )

    @api.model
    def bill_wizard_direct_print_from_payload(
        self,
        payload=None,
        print_format="a4",
        printer_name="",
        printer_id=0,
        selected_printer=None,
    ):
        return self._blocked_super(
            "bill_wizard_direct_print_from_payload",
            payload=payload,
            print_format=print_format,
            printer_name=printer_name,
            printer_id=printer_id,
            selected_printer=selected_printer,
        )

    @api.model
    def bill_wizard_search(self, *args, **kwargs):
        return self._blocked_super("bill_wizard_search", *args, **kwargs)

    @api.model
    def bill_wizard_details(self, header_id):
        return self._blocked_super("bill_wizard_details", header_id)

    @api.model
    def bill_wizard_update_notes(self, header_id, notes=""):
        return self._blocked_super("bill_wizard_update_notes", header_id, notes=notes)

    @api.model
    def bill_wizard_open_return_action(self, header_id):
        return self._blocked_super("bill_wizard_open_return_action", header_id)

    @api.model
    def bill_wizard_render_print_text(self, header_id, print_format="a4"):
        return self._blocked_super(
            "bill_wizard_render_print_text",
            header_id,
            print_format=print_format,
        )

    @api.model
    def bill_wizard_render_print_html(self, header_id, print_format="a4"):
        return self._blocked_super(
            "bill_wizard_render_print_html",
            header_id,
            print_format=print_format,
        )

    @api.model
    def bill_wizard_direct_print(
        self,
        header_id,
        print_format="a4",
        printer_name="",
        printer_id=0,
        selected_printer=None,
    ):
        return self._blocked_super(
            "bill_wizard_direct_print",
            header_id,
            print_format=print_format,
            printer_name=printer_name,
            printer_id=printer_id,
            selected_printer=selected_printer,
        )


class AbSalesPosApi(models.TransientModel):
    _name = "ab_sales_pos_api"
    _inherit = ["ab_sales_pos_api", "ab_sales_prevent.access.mixin"]

    @api.model
    def _blocked_super(self, method_name, *args, **kwargs):
        self._raise_sales_prevented()
        return getattr(super(AbSalesPosApi, self), method_name)(*args, **kwargs)

    @api.model
    def pos_default_employee(self):
        return self._blocked_super("pos_default_employee")

    @api.model
    def pos_load_draft_cache(self, cache_key=None, employee_id=None, pos_hr_session_token=None):
        return self._blocked_super(
            "pos_load_draft_cache",
            cache_key=cache_key,
            employee_id=employee_id,
            pos_hr_session_token=pos_hr_session_token,
        )

    @api.model
    def pos_save_draft_cache(
        self,
        cache_key=None,
        bills=None,
        selected_id=None,
        employee_id=None,
        pos_hr_session_token=None,
    ):
        return self._blocked_super(
            "pos_save_draft_cache",
            cache_key=cache_key,
            bills=bills,
            selected_id=selected_id,
            employee_id=employee_id,
            pos_hr_session_token=pos_hr_session_token,
        )

    @api.model
    def pos_promotions(self, store_id=None, lines=None, applied_program_id=None, manual_clear=False):
        return self._blocked_super(
            "pos_promotions",
            store_id=store_id,
            lines=lines,
            applied_program_id=applied_program_id,
            manual_clear=manual_clear,
        )

    @api.model
    def pos_product_details(self, store_id, product_id):
        return self._blocked_super("pos_product_details", store_id, product_id)

    @api.model
    def pos_barcode_products(self, barcode=None, store_id=None):
        return self._blocked_super("pos_barcode_products", barcode=barcode, store_id=store_id)

    @api.model
    def pos_link_barcode_temp(self, barcode=None, product_ids=None):
        return self._blocked_super("pos_link_barcode_temp", barcode=barcode, product_ids=product_ids)

    @api.model
    def pos_barcode_temp_products(self, barcode=None):
        return self._blocked_super("pos_barcode_temp_products", barcode=barcode)

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        return self._blocked_super("pos_submit", payload=payload, **kwargs)

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None):
        return self._blocked_super(
            "pos_refresh_pos_balances",
            store_id=store_id,
            product_ids=product_ids,
        )

    @api.model
    def pos_customer_lookup(self, phone=None, store_id=None):
        return self._blocked_super("pos_customer_lookup", phone=phone, store_id=store_id)

    @api.model
    def pos_validate_new_customer(self, phone=None, name=None, address=None):
        return self._blocked_super(
            "pos_validate_new_customer",
            phone=phone,
            name=name,
            address=address,
        )

    @api.model
    def pos_customer_create(self, phone=None, name=None, address=None, store_id=None):
        return self._blocked_super(
            "pos_customer_create",
            phone=phone,
            name=name,
            address=address,
            store_id=store_id,
        )


class AbSalesReturnUiApi(models.TransientModel):
    _name = "ab_sales_return_ui_api"
    _inherit = ["ab_sales_return_ui_api", "ab_sales_prevent.access.mixin"]

    @api.model
    def _blocked_super(self, method_name, *args, **kwargs):
        self._raise_sales_prevented()
        return getattr(super(AbSalesReturnUiApi, self), method_name)(*args, **kwargs)

    @api.model
    def open_from_sale_header(self, sale_header_id, **kwargs):
        return self._blocked_super("open_from_sale_header", sale_header_id, **kwargs)

    @api.model
    def get_state(self, return_header_id, **kwargs):
        return self._blocked_super("get_state", return_header_id, **kwargs)

    @api.model
    def save_notes(self, return_header_id, notes="", **kwargs):
        return self._blocked_super("save_notes", return_header_id, notes=notes, **kwargs)

    @api.model
    def update_line(self, return_header_id, line_id, qty_str=None, uom_id=False, **kwargs):
        return self._blocked_super(
            "update_line",
            return_header_id,
            line_id,
            qty_str=qty_str,
            uom_id=uom_id,
            **kwargs,
        )

    @api.model
    def reload_lines(self, return_header_id, **kwargs):
        return self._blocked_super("reload_lines", return_header_id, **kwargs)

    @api.model
    def clear_lines(self, return_header_id, **kwargs):
        return self._blocked_super("clear_lines", return_header_id, **kwargs)

    @api.model
    def total_return_invoice(self, return_header_id, **kwargs):
        return self._blocked_super("total_return_invoice", return_header_id, **kwargs)

    @api.model
    def set_pending(self, return_header_id, **kwargs):
        return self._blocked_super("set_pending", return_header_id, **kwargs)

    @api.model
    def push_to_eplus(self, return_header_id, **kwargs):
        return self._blocked_super("push_to_eplus", return_header_id, **kwargs)

    @api.model
    def abandon_return(self, return_header_id, **kwargs):
        return self._blocked_super("abandon_return", return_header_id, **kwargs)
