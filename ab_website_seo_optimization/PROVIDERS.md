# Provider matrix and verified access references

Documentation checked: **2026-09-28**. Limits are informational snapshots, not promises; administrator caps remain configurable. All listed adapters are implemented. Live accounts were not connected during validation.

“Bulk” means a supported file import from an available export. “Manual” means authorized evidence upload and verification; it does not imply a public API. Commercial review is enforced before pipeline use. Existing optional OpenAI/compatible providers remain supported.

| Provider | Type | Domain | Bulk | API | Free / trial | Quota | Commercial use | Configured | Tested |
|---|---|---|---|---|---|---|---|---|---|
| Egyptian Drug Authority EDDB | DATA_SOURCE | drug, cosmetic, supplement | Manual evidence | No documented API | Public UI / terms | Official search/manual verification; no documented public bulk API verified. | review | Seeded; setup required | Native/normalized fixture; no live call |
| Egyptian Drug Database Dataset A | DATA_SOURCE | drug | Yes | No documented API | Open/public download; terms apply | Public CSV/JSON release; Arabic names are transliterated search aliases. | allowed | Seeded; setup required | Native/normalized fixture; no live call |
| Egyptian Drug Database Dataset B | DATA_SOURCE | drug | Yes | No documented API | Open/public download; terms apply | Public release. Generated usage summaries and safety flags remain unverified context. | permission | Seeded; setup required | Native/normalized fixture; no live call |
| DailyMed | DATA_SOURCE | drug | Yes | Yes | Open/public download; terms apply | Multipart full SPL ZIP releases and daily/weekly/monthly updates; choose a release download URL. | review | Seeded; setup required | SPL parser and mocked XML API; no live call |
| openFDA Drug Label Data | DATA_SOURCE | drug | Yes | Yes | Open/public download; terms apply | 240 requests/minute; 1,000/day without key; 120,000/day with key. Bulk preferred. | allowed | Seeded; setup required | Native/normalized fixture; no live call |
| FDA NDC | DATA_SOURCE | drug | Yes | Yes | Open/public download; terms apply | Same openFDA account/IP quotas; NDC listing is not approval. | allowed | Seeded; setup required | Native/normalized fixture; no live call |
| RxNorm | DATA_SOURCE | drug | Yes | Yes | Open/public download; terms apply | Monthly full release plus ordered weekly RRF updates; public prescribable subset available. | review | Seeded; setup required | Native/normalized fixture; no live call |
| DrugCentral | DATA_SOURCE | drug | Yes | No documented API | Open/public download; terms apply | No guaranteed allowance; configure a conservative local cap. | review | Seeded; setup required | Native/normalized fixture; no live call |
| NIH Dietary Supplement Label Database | DATA_SOURCE | supplement | Yes | Yes | Open/public download; terms apply | Bulk label downloads preferred; no guaranteed unlimited API quota. | allowed | Seeded; setup required | Native/normalized fixture; no live call |
| Open Beauty Facts | DATA_SOURCE | cosmetic | Yes | Yes | Open/public download; terms apply | No guaranteed allowance; configure a conservative local cap. | review | Seeded; setup required | Native/normalized fixture; no live call |
| CosIng | DATA_SOURCE | cosmetic | Manual evidence | No documented API | Public UI / terms | Official ingredient search/export; no documented public API verified. Inventory entry is not an approval. | review | Seeded; setup required | Native/normalized fixture; no live call |
| Cosmetic Ingredient Review | DATA_SOURCE | cosmetic | Manual evidence | No documented API | Public UI / terms | Manual ingredient review with scientific references; no public bulk API verified. | review | Seeded; setup required | Native/normalized fixture; no live call |
| Open Food Facts | DATA_SOURCE | food | Yes | Yes | Open/public download; terms apply | Product reads 100/minute; searches 10/minute. Bulk recommended for large collections. | review | Seeded; setup required | Native/normalized fixture; no live call |
| Open Products Facts | DATA_SOURCE | general | Yes | Yes | Open/public download; terms apply | No guaranteed allowance; configure a conservative local cap. | review | Seeded; setup required | Native/normalized fixture; no live call |
| USDA FoodData Central | DATA_SOURCE | food | Yes | Yes | Open/public download; terms apply | Default 1,000 requests/hour/IP; bulk has no API-key requirement. | allowed | Seeded; setup required | Native/normalized fixture; no live call |
| PubChem | DATA_SOURCE | drug, cosmetic, supplement, food | Yes | Yes | Open/public download; terms apply | At most 5 requests/second; dynamic throttling also applies. | review | Seeded; setup required | Native/normalized fixture; no live call |
| ChEMBL | DATA_SOURCE | drug | Yes | Yes | Open/public download; terms apply | No guaranteed allowance; configure a conservative local cap. | review | Seeded; setup required | Native/normalized fixture; no live call |
| GS1 Verified by GS1 | BARCODE_LOOKUP | drug, cosmetic, supplement, food, general | Manual evidence | No documented API | Public UI / terms | Public UI: 30 single GTIN queries/24h. Automated/bulk access requires separate service terms. | review | Seeded; setup required | Native/normalized fixture; no live call |
| UPCitemdb | BARCODE_LOOKUP | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | Free trial: 100 combined requests/day; burst limits also apply. | review | Seeded; setup required | Native/normalized fixture; no live call |
| openFDA Cosmetic Event Reports | SAFETY_REGULATORY | cosmetic | Yes | Yes | Open/public download; terms apply | Shares openFDA limits. Internal adverse-event context only. | allowed | Seeded; setup required | Mock internal safety isolation; no live call |
| Ready API Trial Enrichment | DATA_SOURCE | drug | No | Yes | Finite trial / free allowance | Finite account/trial allowance; configure from current account. Existing paginated cache retained. | review | Seeded; setup required | Native/normalized fixture; no live call |
| Google Gemini | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | RPM/RPD/TPM depend on model/project/tier; read current AI Studio limits. | review | Seeded; setup required | Mock generation protocol; no live call |
| Groq | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | Select an available model via /models; account-specific RPM/RPD/TPM/TPD. | review | Seeded; setup required | Mock generation protocol; no live call |
| OpenRouter | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | Free models and quotas vary; /models and /key expose availability and account limits. | review | Seeded; setup required | Mock generation protocol; no live call |
| Hugging Face | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | Finite monthly hosted credits; choose an available provider/model. | review | Seeded; setup required | Mock generation protocol; no live call |
| Alibaba Qwen / Model Studio | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | Region/model/account quotas; new Singapore trials expire. Enable Free Quota Only in console. | review | Seeded; setup required | Mock generation protocol; no live call |
| Cohere | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | Trial: 20 chat requests/minute, 1,000 calls/month; evaluation terms. | review | Seeded; setup required | Mock generation protocol; no live call |
| Cloudflare Workers AI | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Finite trial / free allowance | 10,000 neurons/day free; configure model unit costs and account budget. | review | Seeded; setup required | Mock generation protocol; no live call |
| Local AI | LOCAL_MODEL | drug, cosmetic, supplement, food, general | No | Yes | Hardware cost | Local hardware capacity; no external free allowance. | review | Seeded; setup required | Mock generation protocol; no live call |
| OpenAI (existing optional provider) | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | Yes | Paid / account | Existing paid provider retained; configure account limits. | review | Seeded; setup required | Mock generation protocol; no live call |
| Other compatible provider | AI_GENERATOR | drug, cosmetic, supplement, food, general | No | No documented API | Paid / account | Administrator-supplied endpoint and terms. | review | Adapter; add configuration | Mock generation protocol; no live call |

## Provider details

Fields below are also exposed in each provider’s metadata. Model names are configurable. Runtime model discovery is authoritative for availability; source websites and account consoles remain authoritative for quota and license changes.

### Egyptian Drug Authority EDDB (`eda_eddb`)

- Official documentation: [Egyptian Drug Authority EDDB](https://edaegypt.gov.eg/en/services/databases/)
- API: no documented endpoint configured.
- Bulk: manual authorized export only.
- Authentication: None for public data.
- Limits: Official search/manual verification; no documented public bulk API verified.
- License: Review required. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://edaegypt.gov.eg/en/services/databases/)
- Source dimensions: authority `regulatory`; market relevance `egypt`; scope `product`; identifiers `registration,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Egyptian Drug Database Dataset A (`egypt_a`)

- Official documentation: [Egyptian Drug Database Dataset A](https://github.com/karem505/egyptian-drug-database)
- API: no documented endpoint configured.
- Bulk release/file reference: [download](https://raw.githubusercontent.com/karem505/egyptian-drug-database/main/data/egyptian-drugs.csv)
- Authentication: None for public data.
- Limits: Public CSV/JSON release; Arabic names are transliterated search aliases.
- License: CC0 (publisher declaration). Commercial status: `allowed`.
- Terms reference: [source terms/documentation](https://github.com/karem505/egyptian-drug-database)
- Source dimensions: authority `secondary`; market relevance `egypt`; scope `product`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Egyptian Drug Database Dataset B (`egypt_b`)

- Official documentation: [Egyptian Drug Database Dataset B](https://github.com/mahmoudfalous/eg-drugs)
- API: no documented endpoint configured.
- Bulk release/file reference: [download](https://raw.githubusercontent.com/mahmoudfalous/eg-drugs/main/data/eg_drugs.csv)
- Authentication: None for public data.
- Limits: Public release. Generated usage summaries and safety flags remain unverified context.
- License: Noncommercial; separate commercial permission required. Commercial status: `permission`.
- Terms reference: [source terms/documentation](https://github.com/mahmoudfalous/eg-drugs)
- Source dimensions: authority `secondary`; market relevance `egypt`; scope `product`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### DailyMed (`dailymed`)

- Official documentation: [DailyMed](https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm)
- API base: `https://dailymed.nlm.nih.gov/dailymed/services/v2`
- Bulk release/file reference: [download](https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm)
- Authentication: None for public data.
- Limits: Multipart full SPL ZIP releases and daily/weekly/monthly updates; choose a release download URL.
- License: NLM terms; label content rights require review. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm)
- Source dimensions: authority `official`; market relevance `limited`; scope `product`; identifiers `source_id,ndc,rxcui,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### openFDA Drug Label Data (`openfda`)

- Official documentation: [openFDA Drug Label Data](https://open.fda.gov/apis/drug/label/)
- API base: `https://api.fda.gov/drug/label.json`
- Bulk release/file reference: [download](https://api.fda.gov/download.json)
- Authentication: Optional api_key query parameter.
- Limits: 240 requests/minute; 1,000/day without key; 120,000/day with key. Bulk preferred.
- License: Public domain / openFDA terms. Commercial status: `allowed`.
- Terms reference: [source terms/documentation](https://open.fda.gov/terms/)
- Source dimensions: authority `official`; market relevance `limited`; scope `product`; identifiers `source_id,ndc,rxcui,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### FDA NDC (`fda_ndc`)

- Official documentation: [FDA NDC](https://open.fda.gov/apis/drug/ndc/)
- API base: `https://api.fda.gov/drug/ndc.json`
- Bulk release/file reference: [download](https://api.fda.gov/download.json)
- Authentication: Optional api_key query parameter.
- Limits: Same openFDA account/IP quotas; NDC listing is not approval.
- License: Public domain / openFDA terms. Commercial status: `allowed`.
- Terms reference: [source terms/documentation](https://open.fda.gov/terms/)
- Source dimensions: authority `official`; market relevance `limited`; scope `product`; identifiers `source_id,ndc,rxcui,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### RxNorm (`rxnorm`)

- Official documentation: [RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html)
- API base: `https://rxnav.nlm.nih.gov/REST`
- Bulk release/file reference: [download](https://www.nlm.nih.gov/research/umls/licensedcontent/rxnormfiles.html)
- Authentication: Public RxNav; UTS license for full releases.
- Limits: Monthly full release plus ordered weekly RRF updates; public prescribable subset available.
- License: UMLS; source vocabulary restrictions apply. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html)
- Source dimensions: authority `official`; market relevance `limited`; scope `normalization`; identifiers `source_id,rxcui,ndc,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### DrugCentral (`drugcentral`)

- Official documentation: [DrugCentral](https://drugcentral.org/download)
- API: no documented endpoint configured.
- Bulk release/file reference: [download](https://drugcentral.org/download)
- Authentication: None for public data.
- Limits: No guaranteed allowance; configure a conservative local cap.
- License: Creative Commons; verify selected release terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://drugcentral.org/privacy)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `ingredient`; identifiers `source_id,cas,inchi,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### NIH Dietary Supplement Label Database (`dsld`)

- Official documentation: [NIH Dietary Supplement Label Database](https://dsld.od.nih.gov/api-guide)
- API base: `https://dsldapi.od.nih.gov/dsld/v9`
- Bulk release/file reference: [download](https://dsld.od.nih.gov/label-download)
- Authentication: None for public data.
- Limits: Bulk label downloads preferred; no guaranteed unlimited API quota.
- License: CC0 1.0. Commercial status: `allowed`.
- Terms reference: [source terms/documentation](https://dsldapi.od.nih.gov/)
- Source dimensions: authority `official`; market relevance `limited`; scope `product`; identifiers `source_id,gtin,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Open Beauty Facts (`openbeautyfacts`)

- Official documentation: [Open Beauty Facts](https://world.openbeautyfacts.org/data)
- API base: `https://world.openbeautyfacts.org/api/v2/product`
- Bulk release/file reference: [download](https://world.openbeautyfacts.org/data)
- Authentication: None for public data.
- Limits: No guaranteed allowance; configure a conservative local cap.
- License: ODbL; attribution and share-alike; images separate. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://world.openbeautyfacts.org/data)
- Source dimensions: authority `community`; market relevance `limited`; scope `product`; identifiers `gtin,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### CosIng (`cosing`)

- Official documentation: [CosIng](https://single-market-economy.ec.europa.eu/sectors/cosmetics/cosmetic-ingredient-database_en)
- API: no documented endpoint configured.
- Bulk: manual authorized export only.
- Authentication: None for public data.
- Limits: Official ingredient search/export; no documented public API verified. Inventory entry is not an approval.
- License: Review required. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://single-market-economy.ec.europa.eu/sectors/cosmetics/cosmetic-ingredient-database_en)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `ingredient`; identifiers `cas,ec,inci,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Cosmetic Ingredient Review (`cir`)

- Official documentation: [Cosmetic Ingredient Review](https://cir-reports.cir-safety.org/)
- API: no documented endpoint configured.
- Bulk: manual authorized export only.
- Authentication: None for public data.
- Limits: Manual ingredient review with scientific references; no public bulk API verified.
- License: Review required. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://cir-reports.cir-safety.org/)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `ingredient`; identifiers `cas,inci,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Open Food Facts (`openfoodfacts`)

- Official documentation: [Open Food Facts](https://openfoodfacts.github.io/openfoodfacts-server/api/)
- API base: `https://world.openfoodfacts.org/api/v2/product`
- Bulk release/file reference: [download](https://world.openfoodfacts.org/data)
- Authentication: None for public data.
- Limits: Product reads 100/minute; searches 10/minute. Bulk recommended for large collections.
- License: ODbL; attribution and share-alike; images separate. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://openfoodfacts.github.io/openfoodfacts-server/api/)
- Source dimensions: authority `community`; market relevance `limited`; scope `product`; identifiers `gtin,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Open Products Facts (`openproductsfacts`)

- Official documentation: [Open Products Facts](https://world.openproductsfacts.org/data)
- API base: `https://world.openproductsfacts.org/api/v2/product`
- Bulk release/file reference: [download](https://world.openproductsfacts.org/data)
- Authentication: None for public data.
- Limits: No guaranteed allowance; configure a conservative local cap.
- License: ODbL; attribution and share-alike; images separate. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://world.openproductsfacts.org/data)
- Source dimensions: authority `community`; market relevance `limited`; scope `product`; identifiers `gtin,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### USDA FoodData Central (`usda_fdc`)

- Official documentation: [USDA FoodData Central](https://fdc.nal.usda.gov/api-guide/)
- API base: `https://api.nal.usda.gov/fdc/v1`
- Bulk release/file reference: [download](https://fdc.nal.usda.gov/download-datasets/)
- Authentication: data.gov API key for API; public bulk files.
- Limits: Default 1,000 requests/hour/IP; bulk has no API-key requirement.
- License: Public domain / CC0. Commercial status: `allowed`.
- Terms reference: [source terms/documentation](https://fdc.nal.usda.gov/api-guide/)
- Source dimensions: authority `official`; market relevance `limited`; scope `product`; identifiers `source_id,gtin,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### PubChem (`pubchem`)

- Official documentation: [PubChem](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest)
- API base: `https://pubchem.ncbi.nlm.nih.gov/rest/pug`
- Bulk release/file reference: [download](https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/)
- Authentication: None for public data.
- Limits: At most 5 requests/second; dynamic throttling also applies.
- License: Contributor-specific rights; attribution required. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest)
- Source dimensions: authority `scientific`; market relevance `limited`; scope `ingredient`; identifiers `source_id,cas,inchi,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### ChEMBL (`chembl`)

- Official documentation: [ChEMBL](https://chembl.gitbook.io/chembl-interface-documentation/web-services)
- API base: `https://www.ebi.ac.uk/chembl/api/data`
- Bulk release/file reference: [download](https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/)
- Authentication: None for public data.
- Limits: No guaranteed allowance; configure a conservative local cap.
- License: CC BY-SA 3.0. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://chembl.gitbook.io/chembl-interface-documentation/web-services)
- Source dimensions: authority `scientific`; market relevance `limited`; scope `ingredient`; identifiers `source_id,inchi,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### GS1 Verified by GS1 (`gs1`)

- Official documentation: [GS1 Verified by GS1](https://www.gs1.org/services/verified-by-gs1)
- API: no documented endpoint configured.
- Bulk: manual authorized export only.
- Authentication: None for public data.
- Limits: Public UI: 30 single GTIN queries/24h. Automated/bulk access requires separate service terms.
- License: Review required. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://www.gs1.org/docs/verified-by-gs1/public-verified-by-gs1-tou.pdf)
- Source dimensions: authority `identifier`; market relevance `limited`; scope `product`; identifiers `gtin`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### UPCitemdb (`upcitemdb`)

- Official documentation: [UPCitemdb](https://www.upcitemdb.com/wp/docs/main/development/plan/)
- API base: `https://api.upcitemdb.com/prod/trial/lookup`
- Bulk: not advertised.
- Authentication: None for public data.
- Limits: Free trial: 100 combined requests/day; burst limits also apply.
- License: Review required. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://www.upcitemdb.com/wp/docs/main/development/plan/)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `product`; identifiers `gtin`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### openFDA Cosmetic Event Reports (`openfda_cosmetic_event`)

- Official documentation: [openFDA Cosmetic Event Reports](https://open.fda.gov/apis/cosmetic/event/)
- API base: `https://api.fda.gov/cosmetic/event.json`
- Bulk release/file reference: [download](https://api.fda.gov/download.json)
- Authentication: Optional api_key query parameter.
- Limits: Shares openFDA limits. Internal adverse-event context only.
- License: Public domain / openFDA terms. Commercial status: `allowed`.
- Terms reference: [source terms/documentation](https://open.fda.gov/apis/cosmetic/event/)
- Source dimensions: authority `official`; market relevance `limited`; scope `safety`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Ready API Trial Enrichment (`ready_api`)

- Official documentation: [Ready API Trial Enrichment](https://ready-api.vercel.app/apis/drugs-eg)
- API base: `https://ready-api.vercel.app/api/drugs-eg`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Finite account/trial allowance; configure from current account. Existing paginated cache retained.
- License: Review required. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://ready-api.vercel.app/apis/drugs-eg)
- Source dimensions: authority `secondary`; market relevance `egypt`; scope `product`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Models: not applicable.
- Last verified: 2026-09-28.

### Google Gemini (`google_gemini`)

- Official documentation: [Google Gemini](https://ai.google.dev/gemini-api/docs/models)
- API base: `https://generativelanguage.googleapis.com/v1beta`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: RPM/RPD/TPM depend on model/project/tier; read current AI Studio limits.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://ai.google.dev/gemini-api/terms)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Default model: `gemini-3.5-flash`; refresh or select an available model before use.
- Last verified: 2026-09-28.

### Groq (`groq`)

- Official documentation: [Groq](https://console.groq.com/docs/models)
- API base: `https://api.groq.com/openai/v1`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Select an available model via /models; account-specific RPM/RPD/TPM/TPD.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://console.groq.com/docs/deprecations)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Model: administrator selection required.
- Last verified: 2026-09-28.

### OpenRouter (`openrouter`)

- Official documentation: [OpenRouter](https://openrouter.ai/docs/quickstart)
- API base: `https://openrouter.ai/api/v1`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Free models and quotas vary; /models and /key expose availability and account limits.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://openrouter.ai/terms)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Default model: `openrouter/free`; refresh or select an available model before use.
- Last verified: 2026-09-28.

### Hugging Face (`huggingface`)

- Official documentation: [Hugging Face](https://huggingface.co/docs/inference-providers/index)
- API base: `https://router.huggingface.co/v1`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Finite monthly hosted credits; choose an available provider/model.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://huggingface.co/docs/inference-providers/en/pricing)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Model: administrator selection required.
- Last verified: 2026-09-28.

### Alibaba Qwen / Model Studio (`alibaba_qwen`)

- Official documentation: [Alibaba Qwen / Model Studio](https://www.alibabacloud.com/help/en/model-studio/what-is-model-studio)
- API base: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Region/model/account quotas; new Singapore trials expire. Enable Free Quota Only in console.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://www.alibabacloud.com/help/en/model-studio/new-free-quota)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Default model: `qwen-plus`; refresh or select an available model before use.
- Last verified: 2026-09-28.

### Cohere (`cohere`)

- Official documentation: [Cohere](https://docs.cohere.com/v2/reference/chat)
- API base: `https://api.cohere.com/v2`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Trial: 20 chat requests/minute, 1,000 calls/month; evaluation terms.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://docs.cohere.com/v2/docs/rate-limits)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Default model: `command-a-03-2025`; refresh or select an available model before use.
- Last verified: 2026-09-28.

### Cloudflare Workers AI (`cloudflare`)

- Official documentation: [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)
- API base: `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: 10,000 neurons/day free; configure model unit costs and account budget.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Default model: `@cf/meta/llama-3.1-8b-instruct`; refresh or select an available model before use.
- Last verified: 2026-09-28.

### Local AI (`local_ai`)

- Official documentation: [Local AI](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/)
- API base: `http://localhost:8000/v1`
- Bulk: not advertised.
- Authentication: Optional local bearer token.
- Limits: Local hardware capacity; no external free allowance.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Model: administrator selection required.
- Last verified: 2026-09-28.

### OpenAI (existing optional provider) (`openai`)

- Official documentation: [OpenAI (existing optional provider)](https://platform.openai.com/docs/api-reference/chat)
- API base: `https://api.openai.com/v1`
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Existing paid provider retained; configure account limits.
- License: Service and selected model terms. Commercial status: `review`.
- Terms reference: [source terms/documentation](https://platform.openai.com/docs/api-reference/chat)
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Default model: `gpt-4.1-mini`; refresh or select an available model before use.
- Last verified: 2026-09-28.

### Other compatible provider (`other`)

- Official documentation: supplied by administrator.
- API: no documented endpoint configured.
- Bulk: not advertised.
- Authentication: Bearer API key.
- Limits: Administrator-supplied endpoint and terms.
- License: Service and selected model terms. Commercial status: `review`.
- Terms: configure and review the selected service.
- Source dimensions: authority `secondary`; market relevance `limited`; scope `generation`; identifiers `source_id,name`. Completeness is record-dependent; freshness follows each imported release.
- Model: administrator selection required.
- Last verified: 2026-09-28.

## Access and licensing decisions

- EDA and GS1 are verification sources. No unlimited automated or bulk public access is assumed. CosIng and CIR describe ingredients, not registered commercial products.
- Dataset A is a secondary publisher-declared CC0 export; Dataset B has noncommercial restrictions and generated summaries. They are never silently combined.
- Open Facts data carries ODbL attribution/share-alike obligations; images have separate terms. The engine stores provenance but does not implement a legal-compliance publishing service or import images.
- Full RxNorm access requires UTS licensing and attention to source-vocabulary restrictions. Upload authorized releases; no credentials are embedded in download links.
- DrugCentral full database dumps and the largest PubChem/ChEMBL distributions are not executed inside Odoo. Use supported structured exports/SDF and retain release-specific terms.
- US labels, ingredients, chemical relationships and adverse events do not establish Egyptian registration, product efficacy or safety.
- Hosted free/trial tiers can expire. Local inference has hardware and model-license requirements. Review the selected model/service terms before commercial generation.

## Additional protocol references

- [RxNorm RRF fields and relationships](https://www.nlm.nih.gov/research/umls/rxnorm/docs/techdoc.html)
- [RxNorm concept properties](https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.getAllProperties.html)
- [Cohere model discovery](https://docs.cohere.com/reference/list-models)
- [Cloudflare model discovery](https://developers.cloudflare.com/api/resources/ai/subresources/models/methods/list/)

- [DailyMed single-label XML API](https://dailymed.nlm.nih.gov/dailymed/webservices-help/v2/spls_setid_api.cfm)
