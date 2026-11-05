# Account-bound provider credential operation

The versioned bearer controller accepts the optional `get_provider_credentials` operation supplied by Sales Chatter. The existing envelope validation and model authorization remain mandatory. Successful responses carry `Cache-Control: no-store`, including credential responses. Deployments without the extension reject the operation.

Changed file: `controllers/gateway.py`. Real HTTP tests in `ab_crm_sales_workspace/tests/test_credentials.py` verify successful retrieval, mismatched provider rejection and response cache protection.
