/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { OptimizeSEODialog } from "@website/components/dialog/seo";
import wUtils from "@website/js/utils";

const TitleDescription = OptimizeSEODialog.components.TitleDescription;

patch(TitleDescription.prototype, {
    async autoFill() {
        const object = this._getSeoTargetObject();
        if (!object?.id || !object?.model) {
            this._notify("warning", _t("SEO target record was not found."));
            return;
        }
        try {
            const suggestion = await rpc("/ab_website_seo_optimization/seo_component_suggest", {
                res_model: object.model,
                res_id: object.id,
                lang: this.website.currentWebsite.metadata.lang,
                url: this.props.url,
                title: this.seoContext.title || this.props.defaultTitle || "",
                description: this.seoContext.description || "",
                keywords: (this.seoContext.keywords || []).join(","),
                page_text: this._getPageText(),
            });
            this._applySeoSuggestion(suggestion || {});
            this._notify(
                "success",
                _t("SEO fields were generated with %(assistant)s.", {
                    assistant: suggestion.assistant_name || _t("the configured AI assistant"),
                })
            );
        } catch (error) {
            this._notify(
                "danger",
                error?.data?.message || error?.message || _t("The AI assistant could not generate SEO fields.")
            );
        }
    },

    _getSeoTargetObject() {
        const metadata = this.website.currentWebsite.metadata || {};
        return metadata.seoObject || metadata.mainObject;
    },

    _getPageText() {
        const root = this.website.pageDocument.documentElement.querySelector("#wrap, main, body");
        const ignored = [
            /Units in Stock/i,
            /^Price$/i,
            /Terms and Conditions/i,
            /Shipping/i,
            /Business Days/i,
            /\b(LE|EGP)\b/i,
        ];
        return (root?.innerText || "")
            .split(/\n+/)
            .map((line) => line.replace(/\s+/g, " ").trim())
            .filter((line) => line && !line.startsWith("{") && !ignored.some((pattern) => pattern.test(line)))
            .join(" ")
            .slice(0, 3500);
    },

    _applySeoSuggestion(suggestion) {
        if (suggestion.title) {
            this.seoContext.title = suggestion.title;
        }
        if (suggestion.description) {
            this.seoContext.description = suggestion.description;
        }
        if (Array.isArray(suggestion.keywords) && suggestion.keywords.length) {
            this.seoContext.keywords = suggestion.keywords.slice(0, 10);
        }
        if (suggestion.slug && this.props.canEditUrl) {
            this.seoContext.seoName = wUtils.slugify(suggestion.slug);
        }
    },

    _notify(type, message) {
        this.env.services.notification.add(message, { type });
    },
});
