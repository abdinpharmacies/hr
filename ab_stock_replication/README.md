# Stock mapping permissions for replicated products

This optional integration addon permits Inventory Managers and System
Administrators to update only the three stock conversion fields under the
existing product replication policy. Existing product ACLs still apply;
Inventory Manager alone does not grant product write access. Prices, codes,
barcodes and other product fields receive no new replication exception.

It installs automatically when stock integration and Odoo replication are both
installed. It does not enable remote synchronization or alter destinations.
