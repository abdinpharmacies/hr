import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { localOdooUrl } from './connection.mjs';

const configuration = JSON.parse(readFileSync(0, 'utf8'));
const base = localOdooUrl(configuration.url);
process.env.PLAYWRIGHT_BROWSERS_PATH ??= '/opt/playwright/browsers';
const require = createRequire('/opt/playwright/package.json');
const { chromium } = require('playwright');
let browser;
try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`${base.origin}/web/login?db=${encodeURIComponent(configuration.database)}`, {
        waitUntil: 'domcontentloaded', timeout: 60000,
    });
    await page.locator('[name=login]').fill(configuration.login);
    await page.locator('[name=password]').fill(configuration.password);
    await page.locator('button[type=submit]').click();
    await page.waitForURL(url => !url.pathname.startsWith('/web/login'), { timeout: 60000 });
    const response = await context.request.post(`${base.origin}/web/session/get_session_info`, {
        data: { jsonrpc: '2.0', method: 'call', params: {}, id: 1 },
    });
    const session = (await response.json()).result;
    if (session?.uid !== configuration.expectedUserId || session?.db !== configuration.database) {
        throw new Error('Authenticated user/database did not match');
    }
    if (configuration.requireTestName !== false && !session.name?.startsWith('[TEST] ')) {
        throw new Error('Authenticated user display name is not marked as test data');
    }
    console.log(JSON.stringify({ status: 'PASS', user_id: session.uid, database: session.db,
        test_name_verified: session.name?.startsWith('[TEST] ') || false, browser_login_verified: true }));
} catch (error) {
    let message = String(error.message);
    if (configuration.password) message = message.split(configuration.password).join('[REDACTED]');
    console.error(message);
    process.exitCode = 1;
} finally {
    await browser?.close();
}
