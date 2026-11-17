from odoo import Command, fields
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestSupplierClaimWorkflowDiagram(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretarial = new_test_user(
            cls.env, login='diagram_secretarial', password='claim-test-password',
            groups='ab_supplier_claim_cycle.supplier_claim_group_user')
        cls.observer = new_test_user(
            cls.env, login='diagram_inventory', password='claim-test-password',
            groups='ab_supplier_claim_cycle.supplier_claim_group_participant')
        supplier = cls.env['ab_costcenter'].create({
            'name': 'Diagram supplier', 'code': '1-DIAGRAM',
        })
        workflow = cls.env['ab_supplier_claim_workflow'].create({
            'name': 'Diagram workflow',
            'claim_domain': "[('payment_nature', '=', 'cash')]",
            'workflow_stage_ids': [
                Command.create({
                    'name': name,
                    'sequence': sequence,
                    'approver_ids': [Command.set(cls.observer.ids)],
                })
                for name, sequence in (
                    ('Approved branch', 1),
                    ('Pending branch', 1),
                    ('Rejected review', 2),
                    ('Deferred review', 3),
                    ('Waiting review', 4),
                )
            ],
        })
        workflow.action_publish()
        Claim = cls.env['ab_supplier_claim_cycle'].with_user(cls.secretarial)
        claim_values = {
            'supplier_id': supplier.id,
            'num_of_invoice': 1,
            'area': 'north',
            'claim_amount': 100,
            'type_of_invoice': 'original',
            'payment_nature': 'cash',
            'tax_classification': 'non_tax_payment',
            'section': 'medical',
            'claim_month': '2026-11-01',
            'delivery_representative_phone': '01012345678',
            'delivery_representative_name': 'Representative',
            'confirm_contact_info': True,
        }
        cls.open_claim = Claim.create(claim_values)
        cls.open_claim.action_submit()
        statuses = ('approved', 'pending', 'rejected', 'deferred', 'waiting')
        for stage_state, status in zip(cls.open_claim.stage_state_ids, statuses):
            values = {'status': status}
            if status in ('approved', 'rejected', 'deferred'):
                values.update({
                    'user_id': cls.observer.id,
                    'decision_at': fields.Datetime.now(),
                })
            stage_state._internal_write(values)

        cls.closed_claim = Claim.create({**claim_values, 'num_of_invoice': 2})
        cls.closed_claim.action_submit()
        cls.closed_claim.stage_state_ids._internal_write({'status': 'approved'})
        cls.closed_claim._workflow_write({'state': 'closed', 'current_sequence': 0})

    def test_dynamic_workflow_diagram_renders(self):
        self.authenticate(self.observer.login, 'claim-test-password')
        self.browser_js(
            f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.open_claim.id}',
            """
                const deadline = Date.now() + 30000;
                const timer = setInterval(() => {
                    const diagram = document.querySelector('.o_scc_workflow_diagram');
                    const entry = document.querySelector('.o_scc_claim_entry');
                    if (!diagram || !entry) {
                        if (Date.now() > deadline) {
                            clearInterval(timer);
                            console.error('Workflow diagram did not render');
                        }
                        return;
                    }
                    const statuses = ['waiting', 'pending', 'rejected', 'deferred', 'approved'];
                    const stagesAreColored = statuses.every((status) =>
                        diagram.querySelector(
                            `[data-stage-status="${status}"].o_scc_workflow_diagram__node--${status}`
                        )
                    );
                    const parallel = diagram.querySelector(
                        '.o_scc_workflow_diagram__group[data-sequence="1"]'
                    );
                    const orderedGroups = Array.from(
                        diagram.querySelectorAll('.o_scc_workflow_diagram__group[data-sequence]')
                    ).map((node) => node.dataset.sequence).join(',') === '1,2,3,4';
                    const beforeEntry = Boolean(
                        diagram.compareDocumentPosition(entry) & Node.DOCUMENT_POSITION_FOLLOWING
                    );
                    const classification = document.querySelector(
                        '.o_scc_claim_entry .o_scc_classification'
                    );
                    const details = document.querySelector(
                        '.o_scc_claim_entry .o_scc_details'
                    );
                    const actionLabels = Array.from(
                        document.querySelectorAll('.o_scc_workflow_actions .btn')
                    ).map((button) => button.textContent.trim());
                    const dynamicActions = ['Approve Pending branch', 'Reject Pending branch',
                        'Defer Pending branch'].every((label) => actionLabels.includes(label));
                    const actionedStatuses = ['approved', 'rejected', 'deferred'];
                    const actionMetadata = actionedStatuses.every((status) => {
                        const node = diagram.querySelector(`[data-stage-status="${status}"]`);
                        return Boolean(
                            node?.querySelector('.o_scc_workflow_diagram__actor')?.textContent.trim() &&
                            node?.querySelector('.o_scc_workflow_diagram__action-date')?.textContent.trim()
                        );
                    });
                    const cleanHeader = !document.querySelector('.o_scc_form .o_field_statusbar') &&
                        Boolean(document.querySelector('.o_statusbar_buttons .o_scc_workflow_actions'));
                    const arrows = diagram.querySelectorAll('.o_scc_workflow_diagram__arrow').length === 5 &&
                        !diagram.querySelector('.o_scc_workflow_diagram__sequence');
                    const cleanOpenStages = ['pending', 'waiting'].every((status) =>
                        !diagram.querySelector(
                            `[data-stage-status="${status}"] .o_scc_workflow_diagram__action`
                        )
                    );
                    if (stagesAreColored && parallel?.querySelectorAll(
                            '[data-stage-status]'
                        ).length === 2 && orderedGroups && beforeEntry &&
                        classification && details && dynamicActions && actionMetadata &&
                        cleanOpenStages && cleanHeader && arrows &&
                        document.querySelector('.o-mail-Chatter') &&
                        diagram.querySelector('[data-endpoint="draft"] [data-lifecycle-status="completed"]') &&
                        diagram.querySelector('[data-endpoint="closed"] [data-stage-status="waiting"]')) {
                        clearInterval(timer);
                        console.log('test successful');
                    } else if (Date.now() > deadline) {
                        clearInterval(timer);
                        console.error('Workflow diagram content is incorrect', JSON.stringify({
                            stagesAreColored,
                            parallelCount: parallel?.querySelectorAll('[data-stage-status]').length,
                            orderedGroups,
                            beforeEntry,
                            classification: Boolean(classification),
                            details: Boolean(details),
                            dynamicActions,
                            actionMetadata,
                            cleanOpenStages, cleanHeader, arrows,
                            chatter: Boolean(document.querySelector('.o-mail-Chatter')),
                            draft: Boolean(diagram.querySelector(
                                '[data-endpoint="draft"] [data-lifecycle-status="completed"]')),
                            closed: Boolean(diagram.querySelector(
                                '[data-endpoint="closed"] [data-stage-status="waiting"]')),
                        }));
                    }
                }, 100);
            """,
            login=self.observer.login,
        )

    def test_new_incomplete_draft_renders_and_saves(self):
        self.browser_js(
            '/odoo/action-ab_supplier_claim_cycle.invoice_action/new',
            """
                const deadline = Date.now() + 30000;
                let saving = false;
                const timer = setInterval(() => {
                    const month = document.querySelector(
                        '.o_field_widget[name="claim_month"] input[type="text"]');
                    const save = document.querySelector('[aria-label="Save manually"]');
                    if (month && save && !saving) {
                        saving = true;
                        save.click();
                    }
                    if (saving && month && !save && !document.querySelector('.o_error_dialog')) {
                        clearInterval(timer);
                        console.log('test successful');
                    } else if (Date.now() > deadline) {
                        clearInterval(timer);
                        console.error('Incomplete draft did not render and save');
                    }
                }, 100);
            """,
            login=self.secretarial.login,
        )

    def test_actual_arabic_bundle_points_arrows_left(self):
        self.env['res.lang']._activate_lang('ar_001')
        self.observer.lang = 'ar_001'
        self.browser_js(
            f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.open_claim.id}',
            """
                const deadline = Date.now() + 30000;
                const timer = setInterval(() => {
                    const diagram = document.querySelector('.o_scc_workflow_diagram');
                    const arrows = Array.from(document.querySelectorAll(
                        '.o_scc_workflow_diagram__arrow'));
                    const actualRtlBundle = Array.from(document.querySelectorAll(
                        'link[rel="stylesheet"]')).some(link => link.href.includes('.rtl.'));
                    if (diagram?.dir === 'rtl' && actualRtlBundle && arrows.length === 5 &&
                        arrows.every(arrow => {
                            const group = arrow.parentElement.querySelector(
                                '.o_scc_workflow_diagram__group');
                            return getComputedStyle(arrow, '::before').content.includes('←') &&
                                arrow.getBoundingClientRect().left >= group.getBoundingClientRect().right;
                        })) {
                        clearInterval(timer);
                        console.log('test successful');
                    } else if (Date.now() > deadline) {
                        clearInterval(timer);
                        console.error('Actual Arabic bundle has incorrect timeline arrows');
                    }
                }, 100);
            """,
            login=self.observer.login,
        )

    def test_history_view_is_readable(self):
        self.authenticate(self.observer.login, 'claim-test-password')
        self.browser_js(
            f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.open_claim.id}',
            """
                const deadline = Date.now() + 30000;
                const timer = setInterval(() => {
                    const historyTab = document.querySelector('.nav-link[name="history"]');
                    if (!historyTab) {
                        if (Date.now() > deadline) {
                            clearInterval(timer);
                            console.error('History tab did not render');
                        }
                        return;
                    }
                    if (!historyTab.classList.contains('active')) {
                        historyTab.click();
                        return;
                    }
                    const table = document.querySelector('.o_scc_history_table .o_list_table');
                    const sequenceHeader = table?.querySelector('th[data-name="stage_sequence"]');
                    const detailCell = table?.querySelector('td[name="display_note"]');
                    const fillerRows = Array.from(
                        table?.querySelectorAll('tbody tr:not(.o_data_row)') || []
                    );
                    const adjusted = Boolean(table &&
                        table.querySelector('th[data-name="occurred_at"]') &&
                        table.querySelector('th[data-name="user_id"]') &&
                        table.querySelector('th[data-name="event"]') &&
                        table.querySelector('th[data-name="display_note"]') &&
                        (!sequenceHeader || !sequenceHeader.getClientRects().length) &&
                        detailCell && getComputedStyle(detailCell).whiteSpace === 'pre-wrap' &&
                        fillerRows.every((row) => getComputedStyle(row).display === 'none'));
                    if (adjusted) {
                        clearInterval(timer);
                        console.log('test successful');
                    } else if (Date.now() > deadline) {
                        clearInterval(timer);
                        console.error('History table layout is incorrect');
                    }
                }, 100);
            """,
            login=self.observer.login,
        )

    def test_closed_endpoint_renders_as_approved(self):
        self.authenticate(self.observer.login, 'claim-test-password')
        self.browser_js(
            f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.closed_claim.id}',
            """
                const deadline = Date.now() + 30000;
                const timer = setInterval(() => {
                    const closed = document.querySelector(
                        '[data-endpoint="closed"] [data-stage-status="approved"]'
                    );
                    if (closed?.classList.contains('o_scc_workflow_diagram__node--approved')) {
                        clearInterval(timer);
                        console.log('test successful');
                    } else if (Date.now() > deadline) {
                        clearInterval(timer);
                        console.error('Closed endpoint did not render as approved');
                    }
                }, 100);
            """,
            login=self.observer.login,
        )
