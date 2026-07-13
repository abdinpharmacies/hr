/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {patch} from "@web/core/utils/patch";

const SHIPMENT_MODEL = "ab_internal_shipment";
const viewService = registry.category("services").get("view");

if (!viewService.dependencies.includes("notification")) {
    viewService.dependencies = [...viewService.dependencies, "notification"];
}

function isMissingShipmentViewError(error, params) {
    if (params.resModel !== SHIPMENT_MODEL) {
        return false;
    }
    const errorText = [
        error?.name,
        error?.message,
        error?.data?.name,
        error?.data?.message,
        error?.data?.debug,
    ]
        .filter(Boolean)
        .join("\n");
    return (
        /MissingError|Missing Record|Record does not exist/.test(errorText) &&
        /ir\.ui\.view|view/i.test(errorText)
    );
}

function getFallbackViews(views) {
    const requestedTypes = views?.map((view) => view[1]).filter(Boolean) || [];
    const viewTypes = requestedTypes.length ? requestedTypes : ["list", "form"];
    const uniqueTypes = [...new Set(viewTypes)];
    return uniqueTypes.map((viewType) => [false, viewType]);
}

patch(viewService, {
    start(env, services) {
        const service = super.start(env, services);
        const loadViews = service.loadViews.bind(service);

        service.loadViews = async (params, options = {}) => {
            try {
                return await loadViews(params, options);
            } catch (error) {
                if (!isMissingShipmentViewError(error, params)) {
                    throw error;
                }
                services.notification.add(
                    _t("The shipment screen was refreshed because the browser had an outdated view."),
                    {type: "warning"}
                );
                return loadViews(
                    {
                        ...params,
                        views: getFallbackViews(params.views),
                    },
                    options
                );
            }
        };

        return service;
    },
});
