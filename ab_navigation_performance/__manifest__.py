{
    "name": "Storefront Speed Monitor",
    "summary": "Independent live navigation timings and before/after comparisons",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Website",
    "author": "Abdin Pharmacies",
    "developer": "Mohamed Fawzy",
    "depends": ["website"],
    "data": ["views/monitor.xml", "views/menus.xml"],
    "assets": {
        "web.assets_frontend": [
            "ab_navigation_performance/static/src/js/core.js",
            "ab_navigation_performance/static/src/js/requests.js",
            "ab_navigation_performance/static/src/js/collector.js",
            "ab_navigation_performance/static/src/scss/launcher.scss",
        ],
        "ab_navigation_performance.assets_monitor": [
            "web/static/src/module_loader.js",
            "ab_navigation_performance/static/src/js/core.js",
            "ab_navigation_performance/static/src/js/monitor.js",
            "ab_navigation_performance/static/src/scss/monitor.scss",
        ],
    },
    "installable": True,
    "application": True,
}
