// Credentials are supplied as JSON on stdin, never stored in this file.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire('/opt/playwright/package.json');
const { chromium } = require('playwright');
const { url, database, login, password, expectedUserId } = JSON.parse(readFileSync(0, 'utf8'));
const target = new URL(url);
if (!['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname)) {
    throw new Error('Login verification is restricted to the local development server');
}
const browser = await chromium.launch({ headless: true });
try {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`${target.origin}/web/login?db=${encodeURIComponent(database)}`, {
        waitUntil: 'domcontentloaded', timeout: 60000,
    });
    await page.locator('input[name="login"]').fill(login);
    await page.locator('input[name="password"]').fill(password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(u => !u.pathname.startsWith('/web/login'), { timeout: 60000 });
    const response = await context.request.post(`${target.origin}/web/session/get_session_info`, {
        data: { jsonrpc: '2.0', method: 'call', params: {}, id: 1 },
    });
    const body = await response.json();
    if (body.error || body.result?.uid !== expectedUserId || body.result?.db !== database) {
        throw new Error('Authenticated session does not match the requested user and database');
    }
    if (!body.result.name?.startsWith('[TEST] ')) {
        throw new Error('Authenticated user display name is not marked as test data');
    }
    console.log(JSON.stringify({ status: 'PASS', user_id: body.result.uid,
        database: body.result.db, test_name_verified: true, browser_login_verified: true }));
    await context.close();
} finally {
    await browser.close();
}
