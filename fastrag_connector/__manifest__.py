{
    "name": "FastRAG API Connector",
    "version": "19.0.1.0.0",
    "summary": "Connect Odoo to a standalone FastRAG server",
    "depends": ["web"],
    "data": ["security/ir.model.access.csv", "views/fastrag_tester.xml"],
    "external_dependencies": {"python": ["requests"]},
    "license": "LGPL-3",
    "installable": True,
}
