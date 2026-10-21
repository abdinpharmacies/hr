export function callcenterLoginUrl(origin, database, actionId) {
    const url = new URL('/web/login', origin);
    url.searchParams.set('db', database);
    url.searchParams.set('redirect', `/odoo/action-${actionId}`);
    return url.href;
}

export async function openCallcenterAction(page, origin, actionId) {
    const target = new URL(`/odoo/action-${actionId}`, origin);
    const current = new URL(page.url());
    if (current.origin !== target.origin || current.pathname !== target.pathname) {
        await page.goto(target.href);
    }
}
