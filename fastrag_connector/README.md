# FastRAG Odoo connector

Set the FastRAG base URL and API key in Odoo, then use **Test Connection**.
For remote connections, use HTTPS via a reverse proxy and keep FastRAG
on loopback. For same-host development, `http://127.0.0.1:8111` also works.

## TLS for all databases on an Odoo instance

Set these on the **Odoo process**, not as database system parameters or
`odoo.conf` entries. For systemd, add an `Environment=` line under
`[Service]` in an Odoo service drop-in, then reload systemd and restart Odoo.
For an IDE, set the variable in the Odoo run configuration.

- **Publicly trusted certificate:** leave both variables unset.
- **Private CA:** set `Environment=FASTRAG_TLS_CA_BUNDLE=/etc/odoo/certs/fastrag-ca.pem`.
  Use an absolute path to a readable public CA bundle in PEM format on the
  Odoo host. Keep the server's private key on the proxy. The certificate
  must still match the URL hostname or IP.
- **Isolated development only:** set `Environment=FASTRAG_SKIP_TLS_VERIFY=1`
  to skip certificate and hostname verification for FastRAG requests.
  Never set it on production or on an instance shared with production.

Setting both options or configuring an unusable CA bundle fails closed.
The TLS settings apply to every database served by the Odoo process;
the FastRAG base URL and API key remain per database.
