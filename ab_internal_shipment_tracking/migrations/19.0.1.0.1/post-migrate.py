def migrate(cr, version):
    """Clean up all database references to the removed is_receipt_confirmation_user field."""
    # Clean up action window domains
    cr.execute(
        """
        UPDATE ir_act_window
        SET domain = '[(''state'', ''='', ''awaiting_receipt'')]'
        WHERE id IN (
            SELECT res_id
            FROM ir_model_data
            WHERE model = 'ir.actions.act_window'
              AND name = 'ab_internal_shipment_awaiting_receipt_action'
        )
        """
    )

    # Clean up ir.filters referencing the removed field
    cr.execute(
        "DELETE FROM ir_filters WHERE domain ILIKE '%is_receipt_confirmation_user%'"
    )

    # Clean up old model access entries (access_ab_internal_shipment_sender, etc.)
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment%sender'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment%recipient'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment_line%sender'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment_line%recipient'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment_line%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment_history%sender'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment_history%recipient'"
    )
    cr.execute(
        "DELETE FROM ir_model_access WHERE name ILIKE 'ab_internal_shipment_history%department_manager'"
    )

    # Clean up ir.model.data for old model access entries
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment%sender'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment%recipient'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment_line%sender'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment_line%recipient'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment_line%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment_history%sender'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment_history%recipient'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'access_ab_internal_shipment_history%department_manager'"
    )

    # Clean up ir.model.data for old record rule references
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment%relevant_user'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_line%relevant_user'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_line%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_history%relevant_user'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_history%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_user_created'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_user_awaiting_receipt'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_line_user_created'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_line_user_awaiting_receipt'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_history_user_created'"
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE name ILIKE 'rule_ab_internal_shipment_history_user_awaiting_receipt'"
    )

    # Clean up old record rules
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE '%rule_ab_internal_shipment%relevant_user'"
    )
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE '%rule_ab_internal_shipment%department_manager'"
    )
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE 'Internal shipment%created by me'"
    )
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE 'Internal shipment%awaiting my receipt'"
    )
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE 'Internal shipment line%created by me'"
    )
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE 'Internal shipment line%awaiting my receipt'"
    )
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE 'Internal shipment histor%created by me'"
    )
    cr.execute(
        "DELETE FROM ir_rule WHERE name ILIKE 'Internal shipment histor%awaiting my receipt'"
    )
