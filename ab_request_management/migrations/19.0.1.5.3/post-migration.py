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


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ab_request_website
           SET requester_type = CASE
               WHEN COALESCE(NULLIF(TRIM(commercial_register_number), ''), '') != ''
                AND COALESCE(NULLIF(TRIM(employee_code), ''), '') = ''
               THEN 'supplier'
               ELSE 'employee'
           END
         WHERE requester_type IS NULL
            OR requester_type = ''
        """
    )
    _set_model_field_translation(cr, "field_ab_request_website__requester_type", "نوع مقدم الشكوى")
    _set_selection_translation(cr, "field_ab_request_website__requester_type", "employee", "موظف")
    _set_selection_translation(cr, "field_ab_request_website__requester_type", "supplier", "مورد")
