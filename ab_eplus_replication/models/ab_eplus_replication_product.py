import logging
import re
from odoo import models
from odoo.exceptions import ValidationError

ORIGIN_NAMES = {0: "local",
                1: "imported",
                2: "local",
                3: "special_imported",
                4: "local",
                5: "other", }

_logger = logging.getLogger(__name__)


def _get_product_card_name(itm_name):
    if itm_name:
        name = _remove_sub_unit_from_product_name(itm_name)
    else:
        name = "NEW ITEM NOT REGISTERED YET"

    return name


def _get_unit_from_name(name):
    try:
        pattern = r"(\d+\s*)(supp|amp|tab|cap|vial)"
        units = re.findall(pattern, name, re.IGNORECASE)
        return list(flatten_iterable(units))
    except Exception as ex:  # noqa
        return []


def flatten_iterable(target_iter):
    for item in target_iter:
        if is_iterable(item):
            yield from flatten_iterable(item)
        else:
            yield item


def is_iterable(item):
    try:
        iter(item)
    except Exception:  # noqa
        return False
    else:
        return not isinstance(item, str)


def _remove_sub_unit_from_product_name(name):
    pattern = r"(\d+\s*)(supp|amp|tab|cap|vial)"
    match = re.search(pattern, name, flags=re.IGNORECASE)
    if match:
        mod_name = re.sub(pattern=pattern, string=name,
                          repl="", flags=re.IGNORECASE)
        mod_name += f' {match[2]}'
    else:
        mod_name = name
    mod_name = re.sub(pattern=r"\s+", string=mod_name,
                      repl=" ", flags=re.IGNORECASE)
    return mod_name


class ReplicationProduct(models.AbstractModel):
    _inherit = 'ab_eplus_replication'

    def replicate_ab_product(self, replicate_all=False, update_target=None, xrows=10000, commit=False,
                             where_extra_and="", eplus_serials=None, **kw):
        if eplus_serials:
            replicate_all = True

        if replicate_all:
            last_update_date = None
        else:
            last_update_date = self._get_last_update_date(model_name='ab_product')

        products = self._get_products_from_bconnect(last_update_date, xrows, where_extra_and=where_extra_and,
                                                    eplus_serials=eplus_serials)

        for i, chunk_of_products in enumerate(products):
            msg = f"Replicating Products Part {i}"
            self._start_products_replication(chunk_of_products, msg=msg, update_target=update_target,
                                             replicate_all=replicate_all)
            if commit:
                self.env.cr.commit()

    def _get_products_from_bconnect(self, last_update_date, xrows, where_extra_and="", eplus_serials=None):
        where_condition = self._get_where_condition(last_update_date)
        where_condition += where_extra_and
        if eplus_serials:
            serials_str = ','.join(map(str, eplus_serials))
            where_condition += f" and main.itm_id in ({serials_str}) "

        sql = f"""
        SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
        select
            main.itm_code as code,
            iif(mn.itm_name_en='' or mn.itm_name_en is null ,mn.itm_name_ar,mn.itm_name_en) as name,
            main.itm_def_sell_price as default_price,
            main.itm_def_pharm_price + main.itm_def_tax as default_cost,
            main.itm_stop_sell as allow_sale,
            main.itm_stop_pur as allow_purchase,
            main.itm_effictive as effective_material,
            main.itm_origin as origin,
            main.itm_frac_qty as allow_sell_fraction,
            itm_has_expire as has_exp_date,
            itm_ismedicine as is_medicine,
            itm_srvc as is_service,
            itm_freez as is_freeze,
            itm_isprev as is_narcotic,
            itm_allow_discount as allow_discount,
            itm_print_name as allow_print_name,
            itm_notes as description,
            l.u_name_en as u_l_name,
            itm_unit1_unit2 as u_m_num,
            m.u_name_en as u_m_name,
            itm_unit1_unit3 as u_s_num,
            s.u_name_en as u_s_name,
            main.itm_favourite as is_favorite,
            IIF(main.sec_update_date is NULL,main.sec_insert_date,main.sec_update_date) as last_update_date,
            main.itm_id as eplus_serial,
            main.sec_insert_date as eplus_create_date,
            main.itm_active as active
         from Item_Catalog  main
         left join m_name mn on main.itm_id=mn.itm_id
         left join Item_Objects io on io.io_itm_id=main.itm_id
         left join Units L on l.u_id=itm_unit1
         left join Units m on m.u_id=itm_unit2
         left join Units s on s.u_id=itm_unit3
         left join item_usage_manner um on um.ium_id=main.itm_usage_manner_id
         {where_condition}
         order by last_update_date
         """

        yield from self._fetch_eplus_data(sql, last_update_date, xrows)

    def _start_products_replication(self, products, msg="Replicating Products", replicate_all=False, **kw):
        # @todo: separate ab_product_card replication and ab_product replication
        for item in self.web_progress_iter(products, msg=msg):

            # update_target is a list of fields that will be updated
            # e.g, ['is_freeze', 'is_favorite']
            update_target = kw.get('update_target')

            # don't add last_update_date if update_target, as replication must not update it
            always_included_fields = {
                "eplus_serial": item['eplus_serial'],
                "last_update_date": item['last_update_date'],
            }
            if replicate_all:
                always_included_fields.pop('last_update_date', None)

            # Create a dictionary of callable values, so replication does not compute value unless it needs
            product_card_dict = {
                "name": _get_product_card_name(item['name']),
                "effective_material": item['effective_material'],
                "origin": ORIGIN_NAMES.get(item['origin']),
                "has_exp_date": item['has_exp_date'] == 1,
                "is_medicine": item['is_medicine'] == 1,
                "is_service": item['is_service'] == 1,
                "is_freeze": item['is_freeze'] == 1,
                "is_narcotic": item['is_narcotic'] == 1,
                "allow_discount": item['allow_discount'] == 1,
                "allow_print_name": item['allow_print_name'] == 1,
                "description": item['description'],
                "is_favorite": '0' if item['is_favorite'] != 1 else '1',
            }

            if update_target:
                product_card_dict = {field: product_card_dict.get(field) for field in update_target
                                     if field in product_card_dict}

            # add eplus_serial , last_update_date to dict
            product_card_dict.update(always_included_fields)

            product_card = self._get_or_create_record(product_card_dict,
                                                      model_name='ab_product_card', **kw)

            # if it is only update_target not create new records
            if not product_card:
                continue

            # internal function to get uom_small if replication needs that
            def _get_or_create_uom_small():
                u_small_list = _get_unit_from_name(item['name'])
                if u_small_list:
                    u_s_no, u_s_name = u_small_list[:2]
                else:
                    u_s_no, u_s_name = [item['u_s_num'], item['u_s_name']]
                return self._get_or_create_uom(u_name=u_s_name, u_num=u_s_no, u_size="small")

            product_dict = {
                "code": item['code'],
                "default_price": item['default_price'],
                "default_cost": item['default_cost'],
                "u_s_num": item['u_s_num'],
                "u_s_name": item['u_s_name'],
                "unit_l_id": self._get_or_create_uom(u_name=item['u_l_name'], u_num=1, u_size="large").id,
                "unit_m_id": self._get_or_create_uom(u_name=item['u_m_name'], u_num=item['u_m_num'],
                                                     u_size="medium").id,
                "unit_s_id": _get_or_create_uom_small().id,
                "allow_sale": item['allow_sale'] == 0,
                "allow_sell_fraction": item['allow_sell_fraction'] == 0,
                "allow_purchase": item['allow_purchase'] == 0,
                "eplus_create_date": item['eplus_create_date'],
                "product_card_id": product_card.id,
                "active": item['active'] != '0',
            }

            if update_target:
                product_dict = {field: product_dict.get(field) for field in update_target
                                if field in product_dict}

            # add eplus_serial , last_update_date to dict
            product_dict.update(always_included_fields)

            self._get_or_create_record(product_dict, model_name='ab_product', **kw)

    def _get_or_create_uom(self, u_name, u_num, u_size):
        unit_name = u_name.upper()
        uom_type_model = self.env['ab_uom_type'].sudo()
        uom_type = uom_type_model.search([('name', '=', unit_name)], limit=1)

        if not uom_type:
            uom_type = uom_type_model.create({
                'name': unit_name
            })

        uom_model = self.env['ab_uom'].sudo()
        uom = uom_model.search(
            [('unit_no', '=', u_num),
             ('unit_size', '=', u_size),
             ('type_id', '=', uom_type.id)])

        if not uom:
            uom = uom_model.create({
                'unit_no': u_num,
                'unit_size': u_size,
                'type_id': uom_type.id
            })
        return uom
