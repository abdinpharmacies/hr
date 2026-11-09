import {expect, test} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {contains, makeMockEnv, mountWithCleanup, patchWithCleanup} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {LocationCard, DeliveryLocationPicker, locationMapUrl} from "@ab_crm_sales_workspace/location";
import {OrderDialog} from "@ab_crm_sales_workspace/order_dialog";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

defineMailModels();

const location = {latitude: 0, longitude: 0, name: "Customer place", address: "Street", message_id: 5, is_live_snapshot: true, timestamp: "2026-01-01 12:00:00"};

function order(id = 1) {
    return {id, name: `Order ${id}`, state: "draft", revision: 1, edit_version: 2, provider: "telegram", delivery_address: "Address", delivery_notes: "", confirmation: "", lines: [], stores: [], units: {}, audits: [], delivery_location: false, delivery_location_message_id: false};
}

test("location validates map URL including zero, boundaries and invalid values", () => {
    expect(locationMapUrl(location)).toBe("https://www.google.com/maps/search/?api=1&query=0%2C0");
    expect(locationMapUrl({latitude: -90, longitude: 180})).toBe("https://www.google.com/maps/search/?api=1&query=-90%2C180");
    for (const latitude of [NaN, Infinity, true, "0", 91]) expect(locationMapUrl({latitude, longitude: 0})).toBe("");
});

test("location card shows snapshot, copies map link, reports copy failures and isolates coordinates", async () => {
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
    expect("[role=status]").toHaveText("Location link copied.");
    patchWithCleanup(navigator.clipboard, {writeText: async () => { throw new Error("Denied"); }});
    await contains("button:contains(Copy location)").click();
    expect("[role=status]").toHaveText("Could not copy the location. Use Open in Maps to copy the link.");
    await contains("button:contains(Use for delivery)").click();
    expect(copied.at(-1)).toBe("delivery");
    expect(".ab_location_card iframe, .ab_location_card img").toHaveCount(0);
});

test("location handoff opens sole draft and asks for multiple or no drafts without creating", async () => {
    for (const orders of [[{id: 1}], [{id: 1}, {id: 2}], []]) {
        const opened = [];
        const dialogs = [];
        const calls = [];
        const workspace = {state: {detail: {id: 10}, reply: "Unsent text", attachments: [{name: "draft.pdf"}]},
            run: callback => callback(), call: async (model, method) => { calls.push(method); return orders; },
            loadOrder: async (id, point) => opened.push([id, point]), dialog: {add: (component, props) => dialogs.push(props)}};
        await SalesWorkspace.prototype.useLocation.call(workspace, {id: 5, location});
        expect(calls).toEqual(["workspace_location_orders"]);
        expect(opened.length).toBe(orders.length === 1 ? 1 : 0);
        expect(dialogs.length).toBe(orders.length === 1 ? 0 : 1);
        expect(workspace.state.reply).toBe("Unsent text");
        expect(workspace.state.attachments).toEqual([{name: "draft.pdf"}]);
        if (orders.length === 2) { await dialogs[0].select(2); expect(opened[0]).toEqual([2, location]); }
    }
});

test("location chooser creates only after explicit New order", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    let created = 0;
    env.services.dialog.add(DeliveryLocationPicker, {orders: [], select: () => {}, newOrder: async () => created++});
    await animationFrame();
    expect(created).toBe(0);
    await contains("button:contains(New order)").click();
    expect(created).toBe(1);
});

test("location stages over cached edits, survives draft switches and only Save sends source ID", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const first = order();
    const cached = new Map([[1, {order: {...first, delivery_notes: "Unsaved notes", confirmation: "Unsaved confirmation"}, saved: JSON.stringify(first), reprice: false}]]);
    const calls = [];
    let dialog;
    patchWithCleanup(OrderDialog.prototype, {setup() { super.setup(...arguments); dialog = this; }});
    const close = env.services.dialog.add(OrderDialog, {order: first, orders: [{id: 1, name: "One"}, {id: 2, name: "Two"}], cachedDrafts: cached, location, context: {}, onSaved: async () => {}, call: async (model, method, args, kwargs) => {
        calls.push([method, kwargs]);
        if (method === "workspace_data") return order(args[0][0]);
        return {...first, ...kwargs.values, delivery_location: kwargs.values.delivery_location_message_id ? location : false};
    }});
    await animationFrame();
    expect(dialog.state.order.delivery_notes).toBe("Unsaved notes");
    expect(dialog.state.order.delivery_location_message_id).toBe(5);
    expect(calls).toEqual([]);
    await dialog.switchDraft(2);
    await dialog.switchDraft(1);
    expect(dialog.state.order.delivery_location_message_id).toBe(5);
    expect(dialog.state.order.delivery_notes).toBe("Unsaved notes");
    await dialog.save();
    expect(calls.at(-1)[0]).toBe("action_save_draft");
    expect(calls.at(-1)[1].values.delivery_location_message_id).toBe(5);
    expect(calls.at(-1)[1].values.delivery_location).toBe(undefined);
    await contains("button:contains(Remove delivery location)").click();
    expect(dialog.state.order.delivery_location_message_id).toBe(false);
    close();
    await animationFrame();
    expect(cached.get(1).order.delivery_location_message_id).toBe(false);
});
