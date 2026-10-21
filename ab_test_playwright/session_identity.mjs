export function sessionIdentity(payload) {
    return {
        employee_id: payload?.employee?.id ?? null,
        employee_access_id: payload?.profile_id ?? null,
        user_id: payload?.service_user_id ?? null,
        store_id: payload?.store?.id ?? null,
        state: payload?.state ?? null,
    };
}

export function assertEmployeeSession(payload, records, { requireStore = false, token } = {}) {
    const actual = sessionIdentity(payload);
    const expected = {
        employee_id: records.employee_id,
        employee_access_id: records.employee_access_id,
        user_id: records.user_id,
        state: 'active',
    };
    if (requireStore) expected.store_id = records.store_id;
    if (typeof payload?.token !== 'string' || !payload.token || (token && payload.token !== token) ||
        !Number.isInteger(actual.store_id) || actual.store_id <= 0 ||
        Object.entries(expected).some(([key, value]) => actual[key] !== value)) {
        throw new Error(`${requireStore ? 'Branch selection' : 'Employee login'} identity mismatch: expected ${JSON.stringify(expected)}, actual ${JSON.stringify(actual)}; session token must be present and unchanged`);
    }
    return actual;
}

export function assertPageHealthy(errors) {
    if (errors.length) {
        throw new Error('Page/resource errors: ' + errors.map(error =>
            `${error.type}${error.path ? ' ' + error.path : ''}: ${error.message}`).join('; '));
    }
}
