{
    "name": "Abdin eCommerce Storefront",
    "summary": "Abdin-branded storefront for native Odoo eCommerce",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Website/eCommerce",
    "author": "Abdin Pharmacies",
    "developer": "Alhassan Hossny",
    "depends": [
        "ab_website",
        "ab_website_sale_product",
        "website_sale_wishlist",
    ],
    "data": [
        "data/storefront_catalog.xml",
        "views/category_icons.xml",
        "views/layout.xml",
        "views/homepage.xml",
        "views/shop.xml",
        "views/product.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "ab_ecommerce_storefront/static/src/scss/storefront.scss",
        ],
    },
    "installable": True,
    "application": False,
}
