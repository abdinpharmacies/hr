"""
sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin shell -d abdin_replica19 -c /opt/odoo19/odoo19.conf <<'EOF'
env['ab_odoo_replication'].replicate_model('ab_store', replicate_all=True)
env['ir.config_parameter'].create({
'key': 'aaa',
'value': 'bbb'
})
print("Done")
EOF
"""

# UPDATE cron job
commands = """
# stop server

# sql commands
sudo -u odoo19 psql -d abdin_replica19 <<'SQL'
UPDATE ir_act_server s
SET code = 'model.replicate_model(''ab_uom_type'', replicate_all=True)
model.replicate_model(''ab_uom'', replicate_all=True)

model.replicate_model(''ab_product_uom_category'', replicate_all=True)
model.replicate_model(''ab_product_uom'', replicate_all=True)
model.replicate_model(''ab_product_card'', replicate_all=True)
model.replicate_model(''ab_product'', replicate_all=True)
model.replicate_model(''ab_product_barcode'', limit=10000,
                      extra_fields={''product_ids'': ''many2many''})'
FROM ir_cron c
WHERE c.ir_actions_server_id = s.id
  AND c.cron_name = 'ab_odoo_replication_4_product__all';
SQL
"""

commands = """
git -C  /opt/odoo19/custom-addons pull;

# stop server
systemctl stop odoo19.service;

# sql commands
# 
sudo -u odoo19 psql -d abdin_replica19 -c "
UPDATE ir_act_server s
  SET code = $PY$
model.replicate_model('ab_uom_type', replicate_all=True)
model.replicate_model('ab_uom', replicate_all=True)

model.replicate_model('ab_product_uom_category', replicate_all=True)
model.replicate_model('ab_product_uom', replicate_all=True)
model.replicate_model('ab_product_card', replicate_all=True)
model.replicate_model('ab_product', replicate_all=True)
model.replicate_model('ab_product_barcode', limit=10000,
                      extra_fields={'product_ids': 'many2many'})
$PY$
  FROM ir_cron c
  WHERE c.ir_actions_server_id = s.id
    AND c.cron_name = 'ab_odoo_replication_4_product__all';
"

# upgrade current
sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -u ab_store --addons-path=/opt/odoo19/server/addons,/opt/odoo19/custom-addons --stop-after-init;

# install new
sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -i ab_transfer --addons-path=/opt/odoo19/server/addons,/opt/odoo19/custom-addons --stop-after-init;

sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -u ab_transfer --addons-path=/opt/odoo19/server/addons,/opt/odoo19/custom-addons --stop-after-init;

# start server again
systemctl start odoo19.service;
"""

commands = """
git -C  /opt/odoo19/custom-addons pull;

# stop server
systemctl stop odoo19.service;

# sql commands
# sudo -u odoo19 psql -d abdin_replica19 -c "delete from  ir_cron where cron_name like 'ab_odoo_replication_5_contract';"

# upgrade current
sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin  -u ab_odoo_replication -d abdin_replica19  -c /opt/odoo19/odoo19.conf --stop-after-init;
sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin  -u ab_product -d abdin_replica19  -c /opt/odoo19/odoo19.conf --stop-after-init;

# start server again
systemctl start odoo19.service;
"""

# UPDATE cron job
commands = """

# sql commands
sudo -u odoo19 psql -d abdin_replica19 <<'SQL'
select active from ir_cron where cron_name like 'ab_odoo_replication_4_product__all' and active=true;
SQL
"""

commands = r"""
set -e

trap 'sudo systemctl start odoo19.service' EXIT

git -C /opt/odoo19/custom-addons pull

sudo systemctl stop odoo19.service

sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -u ab_promo_program --config /opt/odoo19/odoo19.conf  --stop-after-init

sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -u ab_odoo_replication --config /opt/odoo19/odoo19.conf  --stop-after-init

sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -u ab_sales_doctor --config /opt/odoo19/odoo19.conf  --stop-after-init
"""

commands = r"""
set -e

sudo systemctl restart odoo19.service

sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin module uninstall integration_queue_job -d abdin_replica19 --config /opt/odoo19/odoo19.conf
"""

commands = r"""
set -e

trap 'sudo systemctl start odoo19.service' EXIT

git -C /opt/odoo19/custom-addons pull

sudo systemctl stop odoo19.service

sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -u ab_sales --config /opt/odoo19/odoo19.conf  --stop-after-init
sudo -u odoo19 /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin -d abdin_replica19 -u ab_odoo_replication --config /opt/odoo19/odoo19.conf  --stop-after-init
"""
