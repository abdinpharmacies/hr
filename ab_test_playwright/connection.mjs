import { isIP } from 'node:net';

export function localOdooUrl(value) {
    const target = new URL(value);
    const hostname = target.hostname.replace(/^\[|\]$/g, '');
    const local = hostname === 'localhost' || hostname === '::1' ||
        (isIP(hostname) === 4 && hostname.split('.')[0] === '127');
    if (!['http:', 'https:'].includes(target.protocol) || !local ||
        target.username || target.password || target.pathname !== '/' ||
        target.search || target.hash || target.port === '0' || /\s/.test(value)) {
        throw new Error('Odoo URL must be an HTTP/HTTPS localhost or loopback origin, without credentials, path, query or fragment');
    }
    return target;
}
