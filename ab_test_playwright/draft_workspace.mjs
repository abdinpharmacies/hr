export async function readDraftWorkspace(page, { user_id, employee_id }) {
    return page.evaluate(({ user_id, employee_id }) => {
        const suffix = `_user_${user_id}_employee_${employee_id}_workspace`;
        const keys = Object.keys(sessionStorage).filter(key => key.startsWith('ab_sales_pos_cache_v1_') && key.endsWith(suffix));
        if (keys.length !== 1) throw new Error(`Expected one employee-scoped workspace, found ${keys.length}`);
        const bills = JSON.parse(sessionStorage.getItem(keys[0]));
        if (!Array.isArray(bills)) throw new Error('Invalid draft workspace');
        return { bills, selectedId: sessionStorage.getItem(keys[0].replace(/_workspace$/, '_selection')) };
    }, { user_id, employee_id });
}

export function claimDraft(workspace, previousIds, storeId) {
    const bill = workspace.bills.find(item => item.id === workspace.selectedId);
    if (!bill || previousIds.has(bill.id) || bill.id !== bill.header?.pos_client_token ||
        bill.header.store_id !== storeId || bill.submission?.attempted || bill.lines?.length) {
        throw new Error('Selected bill is not a new empty run-owned draft');
    }
    return bill;
}

export function mayRemoveDraft(workspace, token, owned, protectedTokens) {
    const bill = workspace.bills.find(item => item.id === token);
    return owned.has(token) && !protectedTokens.has(token) && workspace.selectedId === token &&
        bill?.header?.pos_client_token === token && !bill.submission?.attempted && !bill.submission?.local_header_id;
}
