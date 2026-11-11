import {expect, test} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {contains, makeMockEnv, mountWithCleanup, patchWithCleanup} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {LocationCard, locationMapUrl} from "@ab_crm_sales_workspace/location";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

defineMailModels();

const location = {latitude: 0, longitude: 0, name: "Customer place", address: "Street", message_id: 5, is_live_snapshot: true, timestamp: "2026-01-01 12:00:00"};

test("location validates map URL including zero, boundaries and invalid values", () => {
    expect(locationMapUrl(location)).toBe("https://www.google.com/maps/search/?api=1&query=0%2C0");
    expect(locationMapUrl({latitude: -90, longitude: 180})).toBe("https://www.google.com/maps/search/?api=1&query=-90%2C180");
    for (const latitude of [NaN, Infinity, true, "0", 91]) expect(locationMapUrl({latitude, longitude: 0})).toBe("");
});

test("location card shows snapshot, copies map link, reports copy failures and isolates coordinates", async () => {
    await mountWithCleanup(MainComponentsContainer);
    const copied = [];
    patchWithCleanup(navigator.clipboard, {writeText: async value => copied.push(value)});
    await mountWithCleanup(LocationCard, {props: {location, provider: "whatsapp", useDelivery: () => copied.push("delivery")}});
    expect(".ab_location_card.channel-whatsapp").toHaveCount(1);
    expect(".ab_location_card strong").toHaveText("Location snapshot");
    expect(".ab_location_coordinates").toHaveAttribute("dir", "ltr");
    expect(".ab_location_card a").toHaveAttribute("href", locationMapUrl(location));
    expect(".ab_location_card a").toHaveAttribute("rel", "noopener noreferrer");
    expect(".ab_location_card time").not.toHaveText("");
    await contains("button:contains(Copy location)").click();
    expect(copied).toEqual([locationMapUrl(location)]);
    expect(".o_notification:contains(Location link copied.)").toHaveCount(1);
    patchWithCleanup(navigator.clipboard, {writeText: async () => { throw new Error("Denied"); }});
    await contains("button:contains(Copy location)").click();
    expect(".o_notification:contains(Could not copy the location.)").toHaveCount(1);
    await contains("button:contains(Use for delivery)").click();
    expect(copied.at(-1)).toBe("delivery");
    expect(".ab_location_card iframe, .ab_location_card img").toHaveCount(0);
});

test("delivery shortcut passes only its message ID to the POS handoff", async () => {
    const opened = [];
    const workspace = {createOrder: async id => opened.push(id)};
    await SalesWorkspace.prototype.useLocation.call(workspace, {id: 5, location});
    expect(opened).toEqual([5]);
});
