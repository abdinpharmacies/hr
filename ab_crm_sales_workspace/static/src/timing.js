export function traceTiming(stage, correlationIds) {
    if (sessionStorage.getItem('ab_chatter_timing') !== '1') return;
    for (const correlationId of correlationIds.slice(0, 50)) {
        window.dispatchEvent(new CustomEvent('ab-chatter-timing', {
            detail: {stage, correlation_id: correlationId, timestamp_ms: performance.timeOrigin + performance.now()},
        }));
    }
}
