# Website Sales Chatter

Companion to `ab_storefront_callcenter_adapter`. Receives versioned confirmed-order and text-chat events into Sales Chatter, with immutable evidence and company/branch isolation. Website orders sharing a submitted phone display as incoming invoice cards in one customer conversation screen. Agents review the cards and enter products, quantities, units and delivery details manually in POS through the existing contact/header workflow.

Cards have no Create order button. Website-specific POS preparation and the POS quotation panel are removed. Invoice product details show Product, Quantity, Price, Discount and Total. Source unit values remain in the received snapshot and are hidden in Sales Chatter. No product or mapping lookup is performed. Website Orders appears under CRM / OMS; mapping navigation is inactive while existing records and XML IDs remain intact. Existing drafts, invoices, snapshots and historical handoff metadata are retained; direct contact handoffs do not update Website handoff/progress metadata.

See [the setup, security and rollout guide](../docs/website-callcenter-adapter.md). The adapter performs no automatic financial or stock operations. Native portal chat integration and recovery of the two test messages remain suspended.

Delivery addresses display on one line as Governorate | detailed address, followed by the storefront public tracking reference (`sale.order.ab_public_reference`, for example `NO-151126-E4CRGK`). The internal order number remains in the heading. Recognized Egyptian address snapshots resolve the received governorate code to its name; unrecognized addresses retain all received text on one line. Saved snapshots remain unchanged.
