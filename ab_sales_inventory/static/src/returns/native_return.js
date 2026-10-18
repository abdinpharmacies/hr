/** @odoo-module **/
import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';
import '@ab_sales/sales_return/ab_sales_return_ui_api';

const LegacyReturn = registry.category('actions').get('ab_sales.return_ui');

class NativeReturn extends LegacyReturn {
    static template = 'ab_sales_inventory.NativeReturn';

    async pushToEplus() {
        await this._runAction('set_pending', _t('Failed to send the return to cashier.'), {}, _t('Return sent to cashier.'));
    }
}

registry.category('actions').add('ab_sales_inventory.return_ui', NativeReturn);
