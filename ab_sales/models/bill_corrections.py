"""Correct rejected attempts without changing their identity or retry payload."""
from copy import deepcopy
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class CorrectableBill(models.Model):
    _inherit = 'ab_sales_header'

    branch_correction = fields.Json(string='Bill Correction', readonly=True, copy=False, groups='base.group_system')
    branch_submission_history = fields.Json(string='Submission History', readonly=True, copy=False,
                                          groups='base.group_system')

    def _correction_marker(self):
        self.ensure_one()
        data = self.sudo().branch_correction or {}
        if self.status == 'rejected' and data.get('base_revision') == self.branch_request_revision:
            return {key: data[key] for key in ('id', 'base_revision')}
        return False

    def _branch_result(self):
        result = super()._branch_result()
        result['correction'] = self._correction_marker()
        return result


class BillCorrectionApi(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    def _correction_context(self, token, session_token):
        self._pos_require_sales_session(session_token)
        employee, stores = self._draft_scope(pos_hr_session_token=session_token)
        if not employee:
            raise AccessError(_('A valid employee session is required for draft bills.'))
        header = self.env['ab_sales_header'].search(fields.Domain('pos_client_token', '=', str(token or '')), limit=1)
        if not header or header.create_uid != self.env.user or header.store_id.id not in stores:
            raise AccessError(_('You cannot access this draft bill.'))
        if 'pos_hr_employee_id' in header._fields and header.pos_hr_employee_id != employee:
            raise AccessError(_('You cannot access this draft bill.'))
        header.check_access('write')
        record = self._draft_records(employee, stores, tokens=[token], active_only=True)
        if len(record) != 1:
            raise UserError(_('Save this bill to the draft cache before correcting it.'))
        return header, record, employee, stores

    def _confirm_correction_rejection(self, header):
        client = self.env['ab_sales_branch_client']
        config = client._config(header.store_id)
        stored = header.sudo().branch_submission_payload or {}
        target = {'_branch_db_serial': config.db_serial, '_branch_rpc_url': config.rpc_url,
                  '_branch_rpc_db': config.rpc_db, '_branch_store_serial': int(config.store_id.eplus_serial)}
        if not stored or any(stored.get(key) != value for key, value in target.items()):
            raise UserError(_('The branch database changed. Reconcile the original request before retrying.'))
        response = client._call(header.store_id, 'get_sale_statuses', [header.pos_client_token])
        config._validate_identity(response)
        rows = response.get('data')
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise UserError(_('The branch could not confirm that this bill can be corrected. Check its status.'))
        row = dict(rows[0], db_serial=response['db_serial'], store_eplus_serial=response['store_eplus_serial'])
        header._apply_branch_response(row, config)
        if row.get('status') != 'rejected' or row.get('can_edit') is not True:
            raise UserError(_('Only a confirmed rejected bill can be corrected. Check its status.'))
        return config

    def _lock_correction_cache(self, record, revision):
        if not record.try_lock_for_update():
            raise UserError(_('This draft is being edited. Refresh and try again.'))
        record.invalidate_recordset()
        if type(revision) is not int or record.revision != revision:
            raise UserError(_('This draft changed in another window. Refresh before continuing.'))

    def _reserve_correction_slot(self, employee, stores):
        # Same lock and write marker as ordinary draft admission.
        Scope = self.env['ab_sales_pos_draft_scope'].sudo()
        scope = Scope.search(fields.Domain('user_id', '=', self.env.uid)
                             & fields.Domain('employee_key', '=', employee.id), limit=1)
        if not scope:
            scope = Scope.create({'user_id': self.env.uid, 'employee_key': employee.id})
        if not scope.try_lock_for_update():
            raise UserError(_('Draft slots are busy. Try again shortly.'))
        scope.invalidate_recordset()
        scope.write({'revision': scope.revision + 1})
        records = self.env['ab_sales_pos_draft_cache'].sudo().search(
            fields.Domain('user_id', '=', self.env.uid) & fields.Domain('employee_id', '=', employee.id)
            & fields.Domain('state', '=', 'active'))
        permitted = records.filtered(lambda rec: rec.store_id.id in stores)
        bills, _completed = self._draft_authoritative_states([deepcopy(rec.bill_json) for rec in permitted])
        if sum(not bill['slot_locked'] or bool(bill.get('correction')) for bill in bills) + len(records - permitted) >= self._pos_draft_limit():
            raise UserError(_('All draft slots are occupied. Free a slot before correcting this bill.'))

    @api.model
    def pos_begin_bill_correction(self, token, draft_revision, pos_hr_session_token=None):
        header, record, employee, stores = self._correction_context(token, pos_hr_session_token)
        with header._branch_attempt():
            self._lock_correction_cache(record, draft_revision)
            self._confirm_correction_rejection(header)
            if not header._correction_marker():
                self._reserve_correction_slot(employee, stores)
                bill = deepcopy(record.bill_json)
                stored = header.sudo().branch_submission_payload
                if len(bill.get('lines', [])) != len(stored['lines']):
                    raise UserError(_('The cached bill does not match its submitted lines. Reload the original bill.'))
                bill['header'].update(deepcopy(stored['header']))
                bill['header'].setdefault('customer_mode', 'current')
                for line, original in zip(bill['lines'], stored['lines']):
                    line.update(deepcopy(original))
                bill.setdefault('promo', {}).update(applied_id=stored.get('applied_program_id') or False,
                    selected_id=stored.get('applied_program_id') or False,
                    manual_clear=not bool(stored.get('applied_program_id')))
                bill.pop('correction', None)
                data = {'id': str(uuid4()), 'base_revision': header.branch_request_revision,
                        'original_bill': deepcopy(bill)}
                header.sudo()._write_branch_state({'branch_correction': data})
                bill['correction'] = header._correction_marker()
                record.write({'bill_json': bill, 'revision': record.revision + 1})
        result = self._draft_result(employee, record)
        result['bills'], _completed = self._draft_authoritative_states(result['bills'])
        return result

    @api.model
    def pos_cancel_bill_correction(self, token, correction_id, draft_revision, pos_hr_session_token=None):
        header, record, employee, _stores = self._correction_context(token, pos_hr_session_token)
        with header._branch_attempt():
            self._lock_correction_cache(record, draft_revision)
            marker = header._correction_marker()
            if not marker or marker['id'] != correction_id:
                raise UserError(_('This correction is no longer active. Refresh the bill.'))
            original = deepcopy(header.sudo().branch_correction['original_bill'])
            header.sudo()._write_branch_state({'branch_correction': False})
            record.write({'bill_json': original, 'revision': record.revision + 1})
        result = self._draft_result(employee, record)
        result['bills'], _completed = self._draft_authoritative_states(result['bills'])
        return result

    def _validate_correction_bill(self, header, bill):
        marker = header._correction_marker()
        if not marker or bill.get('correction') != marker:
            raise UserError(_('This correction is no longer active. Refresh the bill.'))
        original = header.sudo().branch_correction['original_bill']
        if any((bill['header'].get(key) or False) != (original['header'].get(key) or False)
               for key in set(bill['header']) | set(original['header'])):
            raise UserError(_('Only quantities and the promotion can change in a correction.'))
        lines = bill.get('lines', [])
        if len(lines) != len(original['lines']):
            raise UserError(_('Only quantities and the promotion can change in a correction.'))
        for line, before in zip(lines, original['lines']):
            if any((line.get(key) or False) != (before.get(key) or False)
                   for key in ('product_id', 'sell_price', 'target_sell_price', 'uom_id')):
                raise UserError(_('Only quantities and the promotion can change in a correction.'))

    def _prepare_bill_correction(self, header, incoming):
        """Called inside the submission lock; only server-cached edits are accepted."""
        request = incoming['correction']
        if not isinstance(request, dict):
            raise UserError(_('Invalid bill correction.'))
        stored = header.sudo().branch_submission_payload
        # A lost response must replay this already-frozen revision, never advance again.
        if stored.get('_correction_id') == request.get('id'):
            if request.get('base_revision') != header.branch_request_revision - 1:
                raise UserError(_('Invalid bill correction.'))
            return deepcopy(stored)
        _header, record, _employee, _stores = self._correction_context(
            header.pos_client_token, incoming.get('pos_hr_session_token'))
        self._lock_correction_cache(record, request.get('draft_revision'))
        marker = header._correction_marker()
        if not marker or any(request.get(key) != value for key, value in marker.items()):
            raise UserError(_('This correction is no longer active. Refresh the bill.'))
        self._confirm_correction_rejection(header)
        bill = record.bill_json
        self._validate_correction_bill(header, bill)
        payload = deepcopy(stored)
        wire = payload['_branch_wire_payload']
        for line, original, remote in zip(bill['lines'], payload['lines'], wire['lines']):
            original['qty_str'] = line.get('qty_str') or '1'
            remote['qty_str'] = original['qty_str']
        promotion = bill.get('promo', {}).get('applied_id') or False
        if promotion != (stored.get('applied_program_id') or False):
            wire.pop('promotion', None)
            if promotion:
                wire['promotion'] = self.env['ab_sales_branch_client']._reference(
                    self.env['ab_promo_program'].browse(int(promotion)).exists())
        payload['applied_program_id'] = promotion
        if wire == stored['_branch_wire_payload']:
            raise UserError(_('Change a quantity or promotion before submitting the correction.'))
        self._validate_submission_promotion(payload)
        # Update the local display in place; no sale or sale line is deleted.
        original_lines = header.line_ids.sorted('id')
        if len(original_lines) != len(payload['lines']):
            raise UserError(_('The original bill lines could not be matched.'))
        if 'applied_program_ids' in header._fields:
            header._branch_records().write({'applied_program_ids': [fields.Command.clear()]})
        for line, values in zip(original_lines, payload['lines']):
            if line.product_id.id != values['product_id']:
                raise UserError(_('The original bill lines could not be matched.'))
            line._branch_records().write({'qty_str': values['qty_str']})
        self._pos_apply_payload_promotion(header._branch_records(), payload)
        history = list(header.sudo().branch_submission_history or [])
        history.append({'revision': header.branch_request_revision, 'payload': deepcopy(stored),
                        'message': header.push_message, 'corrected_by': self.env.uid,
                        'corrected_at': fields.Datetime.to_string(fields.Datetime.now())})
        payload['_correction_id'] = marker['id']
        header.sudo()._write_branch_state({'branch_submission_history': history, 'branch_correction': False,
            'branch_request_revision': header.branch_request_revision + 1,
            'branch_submission_payload': payload, 'branch_submission_started': True})
        frozen = deepcopy(bill)
        frozen.pop('correction', None)
        record.write({'bill_json': frozen, 'revision': record.revision + 1})
        return payload

    def _validate_submission_promotion(self, payload):
        """Optional promotion module validates without creating an attempted bill."""
        return True
