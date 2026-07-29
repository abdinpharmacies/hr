def _set_jsonb_translation(cr, table, xml_model, xml_name, field, value):
    cr.execute(
        f"""
        UPDATE {table} AS target
           SET {field} = jsonb_set(
               COALESCE(target.{field}, '{{}}'::jsonb),
               '{{ar_001}}',
               to_jsonb(%s::text),
               true
           )
          FROM ir_model_data AS data
         WHERE data.model = %s
           AND data.module = 'ab_request_management'
           AND data.name = %s
           AND data.res_id = target.id
        """,
        [value, xml_model, xml_name],
    )


def _set_model_field_translation(cr, field_xml_name, value):
    _set_jsonb_translation(
        cr,
        "ir_model_fields",
        "ir.model.fields",
        field_xml_name,
        "field_description",
        value,
    )


def _set_selection_translation(cr, field_xml_name, selection_value, value):
    cr.execute(
        """
        UPDATE ir_model_fields_selection AS selection
           SET name = jsonb_set(
               COALESCE(selection.name, '{}'::jsonb),
               '{ar_001}',
               to_jsonb(%s::text),
               true
           )
          FROM ir_model_data AS data
          JOIN ir_model_fields AS field ON field.id = data.res_id
         WHERE data.model = 'ir.model.fields'
           AND data.module = 'ab_request_management'
           AND data.name = %s
           AND selection.field_id = field.id
           AND selection.value = %s
        """,
        [value, field_xml_name, selection_value],
    )


def _copy_view_arch_translation(cr, view_xml_name):
    cr.execute(
        """
        UPDATE ir_ui_view AS view
           SET arch_db = jsonb_set(
               COALESCE(view.arch_db, '{}'::jsonb),
               '{ar_001}',
               to_jsonb(view.arch_db->>'en_US'),
               true
           )
          FROM ir_model_data AS data
         WHERE data.model = 'ir.ui.view'
           AND data.module = 'ab_request_management'
           AND data.name = %s
           AND data.res_id = view.id
           AND view.arch_db ? 'en_US'
        """,
        [view_xml_name],
    )


def _translate_view_arch_terms(cr, view_xml_name, replacements):
    cr.execute(
        """
        SELECT view.id, COALESCE(view.arch_db->>'ar_001', view.arch_db->>'en_US')
          FROM ir_ui_view AS view
          JOIN ir_model_data AS data
            ON data.model = 'ir.ui.view'
           AND data.module = 'ab_request_management'
           AND data.name = %s
           AND data.res_id = view.id
         WHERE view.arch_db ? 'en_US'
        """,
        [view_xml_name],
    )
    row = cr.fetchone()
    if not row or not row[1]:
        return

    view_id, arch = row
    for source, target in replacements:
        arch = arch.replace(source, target)

    cr.execute(
        """
        UPDATE ir_ui_view
           SET arch_db = jsonb_set(
               COALESCE(arch_db, '{}'::jsonb),
               '{ar_001}',
               to_jsonb(%s::text),
               true
           )
         WHERE id = %s
        """,
        [arch, view_id],
    )


def migrate(cr, version):
    _set_jsonb_translation(
        cr,
        "ir_model",
        "ir.model",
        "model_ab_request_website",
        "name",
        "شكوى خارجية",
    )
    _set_jsonb_translation(
        cr,
        "ir_model",
        "ir.model",
        "model_ab_request_website_followup",
        "name",
        "متابعة الشكوى الخارجية",
    )
    _set_jsonb_translation(
        cr,
        "ir_actions",
        "ir.actions.act_window",
        "ab_request_website_action",
        "name",
        "نموذج الشكاوى",
    )
    _set_jsonb_translation(
        cr,
        "ir_ui_menu",
        "ir.ui.menu",
        "ab_request_management_menu_website_requests",
        "name",
        "الشكاوي",
    )

    for field_xml_name, value in {
        "field_ab_request_website__active": "نشط",
        "field_ab_request_website__commercial_register_number": "رقم السجل التجاري",
        "field_ab_request_website__employee_code": "كود الموظف",
        "field_ab_request_website__followup_ids": "المتابعات",
        "field_ab_request_website__name": "رقم الشكوى الخارجية",
        "field_ab_request_website__national_id": "الرقم القومي",
        "field_ab_request_website_followup__attachment_ids": "المرفقات",
        "field_ab_request_website_followup__create_date": "أنشئ في",
        "field_ab_request_website_followup__create_uid": "أنشئ بواسطة",
        "field_ab_request_website_followup__display_name": "اسم العرض",
        "field_ab_request_website_followup__id": "المعرّف",
        "field_ab_request_website_followup__note": "ملاحظة",
        "field_ab_request_website_followup__request_id": "شكوى خارجية",
        "field_ab_request_website_followup__visible_to_user": "مرئي لمقدم الشكوى",
        "field_ab_request_website_followup__write_date": "آخر تحديث في",
        "field_ab_request_website_followup__write_uid": "آخر تحديث بواسطة",
    }.items():
        _set_model_field_translation(cr, field_xml_name, value)

    _set_selection_translation(cr, "field_ab_request_website__state", "reviewed", "قيد المراجعة")
    _set_selection_translation(cr, "field_ab_request_website__source", "embed", "نموذج الموقع الإلكتروني المضمن")
    _copy_view_arch_translation(cr, "customer_request_followup_lookup")
    _translate_view_arch_terms(
        cr,
        "ab_request_website_view_form",
        [
            ('string="Start Review"', 'string="بدء المراجعة"'),
            ('string="Close"', 'string="إغلاق"'),
            (">External</span>", ">خارجي</span>"),
            ('string="External Requester"', 'string="مقدم الشكوى"'),
            ('string="Classification"', 'string="التصنيف"'),
            ('string="Follow-ups"', 'string="المتابعات"'),
            ('string="Follow-up"', 'string="متابعة"'),
            ('string="Note"', 'string="ملاحظة"'),
            ('placeholder="Write the follow-up note..."', 'placeholder="اكتب ملاحظة المتابعة..."'),
            ('string="Visible to User"', 'string="مرئي لمقدم الشكوى"'),
            ('string="Attachments"', 'string="المرفقات"'),
        ],
    )
