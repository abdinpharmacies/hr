from odoo import api, models


class AbWebsiteSetup(models.AbstractModel):
    _name = "ab.website.setup"
    _description = "Abdin Website Setup"

    @api.model
    def apply(self):
        """Run on module install/upgrade to keep website links and branding aligned."""
        self = self.sudo()
        self._apply_branding_defaults()
        self._sync_top_menus()
        self._patch_footer_links()
        self._disable_website_info_page()
        return True

    def _apply_branding_defaults(self):
        website_name = "Abdin Pharmacies"
        fallback_company_names = {"My Company", "Company name", "My Website"}
        default_facebook = "https://www.facebook.com/AbdinPharmaciesOfficial/"

        for website in self.env["website"].search([]):
            if not website.name or website.name in fallback_company_names:
                website.name = website_name

            company = website.company_id
            if company and (not company.name or company.name in fallback_company_names):
                company.name = website_name
            if company and not company.social_facebook:
                company.social_facebook = default_facebook

    def _sync_top_menus(self):
        menu_model = self.env["website.menu"].sudo()
        forced_menu_urls = {
            "/",
            "/shop",
            "/our-services",
            "/store-locations",
            "/about-us",
            "/contactus",
        }
        hr_applicant_installed = bool(
            self.env["ir.module.module"]
            .sudo()
            .search_count([("name", "=", "ab_hr_applicant"), ("state", "=", "installed")], limit=1)
        )

        root_menus = menu_model.search([("parent_id", "=", False), ("name", "ilike", "menu")])
        for root_menu in root_menus:
            children = menu_model.search(
                [("parent_id", "=", root_menu.id)],
                order="sequence,id",
            )
            max_sequence = max(children.mapped("sequence") or [0])

            for child in children:
                normalized_url = self._to_local_url(child.url)
                if normalized_url != child.url:
                    child.write({"url": normalized_url, "new_window": False})

                if (normalized_url or "") in forced_menu_urls:
                    child.unlink()

            has_jobs_menu = bool(
                menu_model.search_count(
                    [("parent_id", "=", root_menu.id), ("url", "=", "/jobs")],
                    limit=1,
                )
            )
            if hr_applicant_installed and not has_jobs_menu:
                menu_model.create(
                    {
                        "name": "Jobs",
                        "url": "/jobs",
                        "sequence": max_sequence + 200,
                        "new_window": False,
                        "page_id": False,
                        "controller_page_id": False,
                        "parent_id": root_menu.id,
                        "website_id": root_menu.website_id.id,
                    }
                )

    def _disable_website_info_page(self):
        info_main_view = self.env["ir.ui.view"].search([("key", "=", "website.website_info")], limit=1)
        if info_main_view:
            info_main_view.name = "Site Information"

        info_views = self.env["ir.ui.view"].search(
            [("key", "=", "website.show_website_info"), ("active", "=", True)]
        )
        if info_views:
            info_views.write({"active": False})

        info_pages = self.env["website.page"].search([("url", "=", "/website/info")])
        if info_pages:
            info_pages.write({"is_published": False})

    def _patch_footer_links(self):
        footer_views = self.env["ir.ui.view"].search([("key", "=", "website.footer_custom")])
        if not footer_views:
            return

        domain_prefixes = (
            "https://ctrl.abdinpharmacies.com",
            "http://ctrl.abdinpharmacies.com",
            "https://abdinpharmacies.com",
            "http://abdinpharmacies.com",
            "https://www.abdinpharmacies.com",
            "http://www.abdinpharmacies.com",
        )
        for view in footer_views:
            for lang in ("en_US", "ar_001"):
                source = view.with_context(lang=lang).arch_db or ""
                patched = source
                for prefix in domain_prefixes:
                    patched = patched.replace(f'href="{prefix}/', 'href="/')
                    patched = patched.replace(f'href="{prefix}"', 'href="/"')
                    patched = patched.replace(f"&quot;{prefix}/", "&quot;/")
                    patched = patched.replace(f"&quot;{prefix}&quot;", "&quot;/&quot;")
                if patched != source:
                    view.with_context(lang=lang).write({"arch_db": patched})

    @api.model
    def _to_local_url(self, url):
        if not url:
            return url

        prefixes = (
            "https://ctrl.abdinpharmacies.com",
            "http://ctrl.abdinpharmacies.com",
            "https://abdinpharmacies.com",
            "http://abdinpharmacies.com",
            "https://www.abdinpharmacies.com",
            "http://www.abdinpharmacies.com",
        )
        for prefix in prefixes:
            if url.startswith(prefix):
                local_path = url[len(prefix) :] or "/"
                if not local_path.startswith("/"):
                    local_path = f"/{local_path}"
                return local_path
        return url
