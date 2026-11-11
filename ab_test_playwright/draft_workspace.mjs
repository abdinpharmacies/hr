// Observe the tab workspace without mutating application state or shared fallback data.
export async function readDraftWorkspace(page, { user_id, employee_id }) {
    return page.evaluate(({ user_id, employee_id }) => {
        const suffix = `_user_${user_id}_employee_${employee_id}_workspace`;
        const keys = Object.keys(sessionStorage).filter(key =>
            key.startsWith('ab_sales_pos_cache_v1_') && key.endsWith(suffix));
        if (keys.length !== 1) throw new Error(`Expected one scoped POS workspace, found ${keys.length}`);
        const key = keys[0];
        const bills = JSON.parse(sessionStorage.getItem(key));
        if (!Array.isArray(bills)) throw new Error('Invalid POS workspace');
        return {
            bills,
            selectedId: sessionStorage.getItem(key.replace(/_workspace$/, '_selection')) || null,
        };
    }, { user_id, employee_id });
}
