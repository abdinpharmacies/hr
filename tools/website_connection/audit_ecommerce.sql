\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT e.name, e.source, e.enabled, w.domain AS website,
       (SELECT COUNT(*) FROM sale_order s WHERE s.ab_callcenter_endpoint_id = e.id) AS linked_orders,
       (SELECT COUNT(*) FROM ab_storefront_callcenter_event v WHERE v.endpoint_id = e.id) AS order_events,
       (SELECT COUNT(*) FROM ab_storefront_callcenter_event v WHERE v.endpoint_id = e.id AND NOT v.acknowledged) AS pending_order_events,
       (SELECT COUNT(*) FROM ab_storefront_callcenter_chat_event v WHERE v.endpoint_id = e.id AND NOT v.acknowledged) AS pending_chat_events,
       (SELECT COUNT(*) FROM ab_storefront_callcenter_lifecycle v WHERE v.endpoint_id = e.id AND NOT v.acknowledged) AS pending_lifecycle_events
FROM ab_storefront_callcenter_endpoint e
LEFT JOIN website w ON w.id = e.website_id
WHERE e.source IN ('62c18ac9-3a5b-472d-a75c-86d8edb575f5', '2f3d9e8a-a652-4203-b440-eff49207a3a4', 'a4e63f7a-c5d5-4d13-927b-0a40c287253f')
ORDER BY e.source;
SELECT COUNT(DISTINCT first_event.order_id) AS orders_recorded_under_both_sources
FROM ab_storefront_callcenter_event first_event
JOIN ab_storefront_callcenter_endpoint first_endpoint ON first_endpoint.id = first_event.endpoint_id
JOIN ab_storefront_callcenter_event second_event ON second_event.order_id = first_event.order_id
JOIN ab_storefront_callcenter_endpoint second_endpoint ON second_endpoint.id = second_event.endpoint_id
WHERE first_endpoint.source = '62c18ac9-3a5b-472d-a75c-86d8edb575f5'
  AND second_endpoint.source IN ('2f3d9e8a-a652-4203-b440-eff49207a3a4', 'a4e63f7a-c5d5-4d13-927b-0a40c287253f');
COMMIT;
