(async () => {
    if (location.hostname !== "abdinpharmacies.com") {
        throw new Error("Open abdinpharmacies.com while signed in, then run this script.");
    }

    const rpc = async (method, args = [], kwargs = {}) => {
        const response = await fetch(`/web/dataset/call_kw/product.template/${method}`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { model: "product.template", method, args, kwargs },
                id: Date.now(),
            }),
        });
        if (!response.ok) {
            throw new Error(`product.template.${method}: HTTP ${response.status}`);
        }
        const result = await response.json();
        if (result.error) {
            throw new Error(`${method}: ${result.error.data?.message || result.error.message}`);
        }
        return result.result;
    };

    const catalog = await rpc("fields_get", [], { attributes: ["type"] });
    const publicationField = ["is_published", "website_published"]
        .find((name) => catalog[name]?.type === "boolean");
    if (!publicationField || catalog.default_code?.type !== "char") {
        throw new Error("Publication status or product code is unavailable on the old website.");
    }

    const domain = [[publicationField, "=", true]];
    const before = await rpc("search_count", [domain], { context: { active_test: false } });
    const products = [];
    let lastId = 0;
    while (true) {
        const batch = await rpc("search_read", [], {
            domain: [...domain, ["id", ">", lastId]],
            fields: ["id", "default_code", "name"],
            limit: 500,
            order: "id asc",
            context: { active_test: false },
        });
        if (!batch.length) {
            break;
        }
        products.push(...batch);
        lastId = batch[batch.length - 1].id;
    }
    const after = await rpc("search_count", [domain], { context: { active_test: false } });
    if (before !== after || products.length !== before) {
        throw new Error("Published products changed during export. Please run it again.");
    }

    const payload = {
        source: location.origin,
        exported_at: new Date().toISOString(),
        model: "product.template",
        publication_field: publicationField,
        published_count: products.length,
        products,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `legacy_published_products_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    console.log(`Downloaded ${products.length} published products`);
})().catch((error) => console.error("Publication export stopped:", error));
