import { isIP } from 'node:net';

export function localOdooUrl(value) {
    let url;
    try { url = new URL(value); } catch { throw new Error('Invalid local Odoo URL'); }
    const host = url.hostname.replace(/^\[|\]$/g, '');
    const local = host === 'localhost' || host === '::1' || (isIP(host) === 4 && host.startsWith('127.'));
    if (!local || !['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.pathname !== '/' || url.search || url.hash || url.port === '0' || /\s/.test(value)) {
        throw new Error('Use a localhost or loopback origin without credentials, path, query, or fragment');
    }
    return url;
}
