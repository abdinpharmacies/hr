import { _t } from '@web/core/l10n/translation';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { patch } from '@web/core/utils/patch';

import {ControlPanel} from '@web/search/control_panel/control_panel';

patch(ControlPanel.prototype, {
    checkRefreshAvailability() {
        return ['kanban', 'list', 'form'].includes(this.env.config.viewType);
    },
    async onRefreshClick() {
        if (await this.hasRefreshUnsavedChanges()) {
            this.openRefreshUnsavedChangesDialog();
            return;
        }
        await this.refreshCurrentView();
    },
    async hasRefreshUnsavedChanges() {
        const root = this.env?.model?.root;
        if (!root) {
            return false;
        }
        if (typeof root.isDirty === 'function') {
            return await root.isDirty();
        }
        return Boolean(root.dirty || root.editedRecord);
    },
    openRefreshUnsavedChangesDialog() {
        this.dialogService.add(ConfirmationDialog, {
            title: _t("Refresh View"),
            body: _t("Refreshing will delete your unsaved changes. Save them before refreshing, or continue and lose the unsaved changes."),
            confirmLabel: _t("Save Changes"),
            confirm: async () => {
                if (!(await this.saveRefreshUnsavedChanges())) {
                    return false;
                }
                await this.refreshCurrentView();
            },
            cancelLabel: _t("Refresh Anyway"),
            cancel: async () => {
                await this.discardRefreshUnsavedChanges();
                await this.refreshCurrentView();
            },
            dismiss: () => {},
        });
    },
    async saveRefreshUnsavedChanges() {
        const root = this.env?.model?.root;
        if (root?.editedRecord && typeof root.leaveEditMode === 'function') {
            return await root.leaveEditMode();
        }
        if (typeof root?.save === 'function') {
            return await root.save();
        }
        return true;
    },
    async discardRefreshUnsavedChanges() {
        const root = this.env?.model?.root;
        if (root?.editedRecord && typeof root.leaveEditMode === 'function') {
            await root.leaveEditMode({ discard: true });
            return;
        }
        if (typeof root?.discard === 'function') {
            await root.discard();
        }
    },
    async refreshCurrentView() {
        if (this.env?.config?.viewType === 'form') {
            const model = this.env?.model;
            if (model?.load) {
                await model.load();
                if (typeof model.notify === 'function') {
                    model.notify();
                }
                return;
            }
            if (model?.root?.load) {
                await model.root.load();
                if (typeof model.notify === 'function') {
                    model.notify();
                }
                return;
            }
        }
        if (this.pagerProps?.onUpdate) {
            await this.pagerProps.onUpdate({
                offset: this.pagerProps.offset,
                limit: this.pagerProps.limit
            });
        } else if (typeof this.env.searchModel?.search === 'function') {
            await this.env.searchModel.search();
        }
    },
});
