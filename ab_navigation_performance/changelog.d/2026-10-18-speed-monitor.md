# Independent storefront speed monitor

## Recent relevant commits

No previous commits exist for this new module. The module follows the minimal `ab_template` scaffold; ownership remains Abdin Pharmacies and developer metadata is Mohamed Fawzy.

## Current changes before commit:

- Add a standalone Odoo application, **Storefront Speed Monitor**, with an English/Arabic interface and a Website configuration shortcut.
- Open `/ab/performance` in a separate window. The admin-only floating website control starts/stops tracking with one button and opens the same named results window through a separate link. Recording continues when the results window is closed.
- Record before/after visits, stop recording without deleting results, view per-page means and improvement percentages, and export a JSON report. Clearing records requires confirmation in the interface.
- Keep measurements in browser local storage, scoped by database, user, website and company. Update the monitor through browser storage events across windows, without telemetry requests or server-side measurement records. Keep up to 200 visits and 500 background requests in separate bounded stores. Page-load samples start with the next full-page navigation; fetch/AJAX collection starts immediately on the current page.
- Capture browser navigation TTFB, FCP, load and the latest LCP candidate. Compare matching paths, URL-query fingerprints, language, viewport, pixel ratio and navigation type. Exclude background loads, back/forward-cache restores and unavailable query fingerprints from averages. Missing metrics remain missing rather than becoming zero.
- Add a live endpoint table grouped by path, request type and phase, with request count, mean duration, slowest duration, mean first response and latest source page. Export individual request samples and both phase summaries alongside page comparisons. Endpoint summaries include background activity and combine query filters; controlled page comparisons retain their stricter matching.
- Observe same-origin fetch/XMLHttpRequest Resource Timing entries without replacing browser network APIs or generating probe requests. Ignore resources such as images/scripts, requests predating recording, other origins and the monitor itself. Flush queued completed entries on local stop/page hide, and stop collecting across windows. Show unsupported-browser and storage errors in the floating control.
- Hash URL queries rather than storing query values; redact long hexadecimal identifier segments in paths. The exported report stays local until the user chooses to share it.
- Enforce System Administrator access in the GET controller and restrict both menus and the website launcher. The module adds no models, groups, ACL grants, hooks, cron jobs, external connections, stock changes or pricing changes.
- Depend only on `website`; installing this tool does not require upgrading `ab_ecommerce_storefront` or deploying its pending performance changes.

Files changed:

- `ab_navigation_performance/__init__.py`
- `ab_navigation_performance/__manifest__.py`
- `ab_navigation_performance/controllers/__init__.py`
- `ab_navigation_performance/controllers/monitor.py`
- `ab_navigation_performance/views/menus.xml`
- `ab_navigation_performance/views/monitor.xml`
- `ab_navigation_performance/static/src/js/core.js`
- `ab_navigation_performance/static/src/js/requests.js`
- `ab_navigation_performance/static/src/js/collector.js`
- `ab_navigation_performance/static/src/js/monitor.js`
- `ab_navigation_performance/static/src/scss/launcher.scss`
- `ab_navigation_performance/static/src/scss/monitor.scss`
- `ab_navigation_performance/static/description/icon.png`
- `ab_navigation_performance/i18n/ar.po`
- `ab_navigation_performance/i18n/ar_001.po`
- `ab_navigation_performance/changelog.d/2026-10-18-speed-monitor.md`

## Validation

- Activated the endpoint-tracking update with a targeted upgrade of `ab_navigation_performance` on development database `ecom19` (port 4092), without stopping the running Odoo service. Upgrade completed successfully; log: `/tmp/ab-navigation-endpoints-activation.log`. Request a one-time refresh of already-open store pages to load the new controls and collector.

- Installed only `ab_navigation_performance` on the selected development database `ecom19` serving port 4092, with `--stop-after-init --no-http`, zero workers/cron threads and alternate port arguments. The existing Odoo process was not stopped or restarted. The live `/ab/performance` route returned HTTP 303 to sign-in for an anonymous request. Activation log: `/tmp/ab-navigation-activation.log`.
- Targeted installation and upgrades passed on the separate `ecom19_home_ux_20261015` development database with the ecommerce addon checkout, no HTTP listener, zero cron threads and alternate port arguments 5369/5372.
- Six rollback-only Odoo tests passed: admin access and no-cache headers, direct-route rejection for internal/portal/public users, bilingual standalone rendering, and menu permissions/translation. An anonymous HTTP request redirects to sign-in. The independent root application menu was checked separately.
- Twenty-two Node tests passed for persistent controls, user/site isolation, arithmetic, missing values, regressions, comparison grouping, background/cache exclusions, storage bounds, corrupt rows, collector timings, late starts, observer fallback, cross-window stop, cache restores, inactive recording, floating start/stop, immediate request recording, URL privacy, buffered/asset/cross-origin exclusions, request stop/restart boundaries, queued-entry flush/deduplication, unsupported browsers, independent request retention and endpoint aggregation.
- The complete website frontend asset bundles compiled in English and Arabic, with the request observer and collector present in JavaScript and the floating-control styles present in CSS. The validation clone still reports unrelated missing filestore attachments; the resulting checked bundles contained the intended module code/styles and no CSS compilation errors.
- Generated English and RTL monitor CSS bundles returned 200 and contained the intended styles; the JavaScript bundle returned 200 and contained both application modules. A Sass unit conflict found during validation was corrected and compilation rechecked.
- Odoo POT export supplied the translation references; all 56 current extracted terms are translated; 19 new entries were merged while preserving existing translations in both Arabic catalogs. Both passed `msgfmt --check-format`, and `ar_001` rendered the Arabic title and RTL layout. The root menu reuses the same translated title, and the new endpoint heading was checked in English and Arabic at runtime.
- Python/XML/manifest parsing and JavaScript syntax checks passed. No connected browser was available for a real visual/window interaction test; cross-window behavior was exercised with simulated browser events. Test harnesses and logs are under `/tmp/ab-navigation-*`, outside the runtime addon. No production archive was generated.

## Usage and limits

1. Sign in as a System Administrator and refresh the store once after upgrading. Click **Start tracking** on the floating control, browse normally, then click the same button (**Stop tracking**) to stop. This starts a Before recording.
2. Open **Results** or `/ab/performance` to see endpoint timings and page visits. The monitor also has a single start/stop button and a Before/After phase selector. Use the same browser origin and account. Repeat each page at least three times for comparisons.
3. Stop recording, make the intended change, select **After** in the monitor, start tracking, and repeat the same pages under matching conditions. Positive improvement means lower mean time.
4. Export the report before clearing measurements or site storage. Records persist across navigation and browser reopening; they are not stored in PostgreSQL or shared between devices.

This tool measures full website page navigations and completed same-origin fetch/AJAX network requests while recording. Request duration does not measure screen rendering. Odoo backend screens, other origins, WebSockets, requests still in flight when recording stops, and screen changes without requests are outside its scope. LCP is a candidate observation, not a complete Core Web Vitals implementation. It neither automates browsing nor changes cache/network settings. Keep those conditions consistent yourself. Popup blocking may open the monitor in a regular tab instead; it can be moved into a separate window.
