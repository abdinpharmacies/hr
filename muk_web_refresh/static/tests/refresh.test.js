import { expect, test } from '@odoo/hoot';
import {
    models,
    fields,
    defineModels,
    mountView,
    onRpc,
    contains,
} from '@web/../tests/web_test_helpers';

class Product extends models.Model {
    name = fields.Char();
    _records = [
        { id: 1, name: 'Test 1' },
        { id: 2, name: 'Test 2' },
    ];
}
defineModels({ Product });

onRpc('has_group', () => true);

test(
    'refresh button reloads without active state',
    async () => {
        onRpc('web_search_read', () => {
            expect.step('web_search_read');
        });
        await mountView({
            type: 'list',
            resModel: 'product',
            arch: `<list><field name='name'/></list>`,
        });
        expect.verifySteps(['web_search_read']);
        expect('.o_control_panel .o_muk_web_refresh_button').toHaveCount(1);
        expect('.o_control_panel i.fa-refresh').toHaveCount(1);
        expect('.o_control_panel i.fa-refresh').not.toHaveClass('fa-spin');
        await contains('.o_control_panel i.fa-refresh').click();
        expect.verifySteps(['web_search_read']);
        expect('.o_control_panel i.fa-refresh').not.toHaveClass('fa-spin');
});

test(
    'dirty form refresh can save changes before reloading',
    async () => {
        onRpc('web_read', () => {
            expect.step('web_read');
        });
        onRpc('web_save', () => {
            expect.step('web_save');
        });
        await mountView({
            type: 'form',
            resModel: 'product',
            resId: 1,
            arch: `<form><field name='name'/></form>`,
        });
        expect.verifySteps(['web_read']);
        await contains('.o_field_widget[name=name] input').edit('Updated');
        await contains('.o_control_panel i.fa-refresh').click();
        expect('.modal-title').toHaveText('Refresh View');
        expect('.modal-body').toHaveText('Refreshing will delete your unsaved changes. Save them before refreshing, or continue and lose the unsaved changes.');
        expect('.modal-footer .btn-primary').toHaveText('Save Changes');
        expect('.modal-footer .btn-secondary').toHaveText('Refresh Anyway');
        expect.verifySteps([]);
        await contains('.modal-footer .btn-primary').click();
        expect.verifySteps(['web_save', 'web_read']);
});

test(
    'dirty form refresh can discard changes before reloading',
    async () => {
        onRpc('web_read', () => {
            expect.step('web_read');
        });
        onRpc('web_save', () => {
            throw new Error('should not save when refreshing anyway');
        });
        await mountView({
            type: 'form',
            resModel: 'product',
            resId: 1,
            arch: `<form><field name='name'/></form>`,
        });
        expect.verifySteps(['web_read']);
        await contains('.o_field_widget[name=name] input').edit('Discarded');
        await contains('.o_control_panel i.fa-refresh').click();
        await contains('.modal-footer .btn-secondary').click();
        expect.verifySteps(['web_read']);
});
