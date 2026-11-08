(async () => {
    if (location.hostname !== "abdinpharmacies.com") {
        throw new Error("Open abdinpharmacies.com while signed in, then run this script.");
    }

    const rpc = async (model, method, args = [], kwargs = {}) => {
        const response = await fetch(`/web/dataset/call_kw/${model}/${method}`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { model, method, args, kwargs },
                id: Date.now(),
            }),
        });
        if (!response.ok) {
            throw new Error(`${model}.${method}: HTTP ${response.status}`);
        }
        const result = await response.json();
        if (result.error) {
            throw new Error(`${model}.${method}: ${result.error.data?.message || result.error.message}`);
        }
        return result.result;
    };

    const attributes = ["string", "type", "translate", "relation"];
    const [templateFields, variantFields] = await Promise.all([
        rpc("product.template", "fields_get", [], { attributes }),
        rpc("product.product", "fields_get", [], { attributes }),
    ]);
    const relevant = /seo|meta|keyword|canonical|slug|description|og_|twitter/i;
    const textTypes = new Set(["char", "text", "html", "selection"]);
    const candidates = Object.entries(templateFields)
        .filter(([name, info]) => textTypes.has(info.type) && relevant.test(`${name} ${info.string || ""}`))
        .map(([name]) => name);
    const variantCandidates = Object.entries(variantFields)
        .filter(([name, info]) => textTypes.has(info.type) && relevant.test(`${name} ${info.string || ""}`))
        .map(([name]) => name);
    const languages = await rpc("res.lang", "search_read", [], {
        domain: [["active", "=", true]],
        fields: ["code", "name"],
        limit: 100,
    });
    const selectedLanguages = ["en_US", ...languages.map((language) => language.code).filter((code) => /^ar(?:_|$)/i.test(code))];
    const uniqueLanguages = [...new Set(selectedLanguages)];
    const fields = [...new Set(["id", "default_code", "name", "write_date", ...candidates])]
        .filter((name) => Object.hasOwn(templateFields, name));
    const data = {};

    for (const lang of uniqueLanguages) {
        const records = [];
        let lastId = 0;
        while (true) {
            const batch = await rpc("product.template", "search_read", [], {
                domain: [["id", ">", lastId]],
                fields,
                limit: 200,
                order: "id asc",
                context: { lang, active_test: false },
            });
            if (!batch.length) {
                break;
            }
            records.push(...batch);
            lastId = batch[batch.length - 1].id;
            if (records.length % 1000 === 0) {
                console.log(`${lang}: ${records.length} products read`);
            }
        }
        data[lang] = records;
    }

    const output = {
        source: location.origin,
        exported_at: new Date().toISOString(),
        model: "product.template",
        template_field_catalog: templateFields,
        variant_field_catalog: variantFields,
        template_candidate_fields: candidates,
        variant_candidate_fields: variantCandidates,
        languages: uniqueLanguages,
        products_by_language: data,
    };
    const blob = new Blob([JSON.stringify(output)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `legacy_product_seo_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    console.log(`Downloaded ${link.download}`, Object.fromEntries(Object.entries(data).map(([lang, rows]) => [lang, rows.length])));
})().catch((error) => console.error("SEO export stopped:", error));
