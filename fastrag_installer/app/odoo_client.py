import asyncio
import httpx
from .contracts import API_VERSION


class BackendError(Exception):
    """Safe error text: never includes backend tracebacks, headers or secrets."""


class OdooClient:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.url + "/", timeout=settings.timeout_seconds,
            follow_redirects=False, transport=transport,
            headers={"Authorization": "bearer " + settings.api_key.get_secret_value(),
                     "X-Odoo-Database": settings.database, "Content-Type": "application/json"},
        )

    async def close(self):
        await self.client.aclose()

    async def call(self, method, **payload):
        # Only methods defined by this service's addon; never arbitrary model RPC.
        allowed = {"capabilities", "upload_document", "job_status", "claim_job", "renew_job",
                   "complete_index", "complete_answer", "fail_job", "search_chunks", "save_answer", "job_file"}
        if method not in allowed:
            raise ValueError("Unsupported backend operation")
        read_only = method in {"capabilities", "job_status", "search_chunks", "job_file"}
        for attempt in range(3 if read_only else 1):
            try:
                response = await self.client.post("json/2/fastrag.backend/api_" + method, json=payload)
                if response.status_code in {401, 403}:
                    raise BackendError("Odoo authentication or permission denied")
                if response.status_code in {429, 502, 503, 504} and read_only and attempt < 2:
                    await asyncio.sleep(0.25 * (2 ** attempt))
                    continue
                if response.is_error:
                    raise BackendError(f"Odoo rejected {method} (HTTP {response.status_code}); inspect the Odoo log")
                try:
                    result = response.json()
                except ValueError as exc:
                    raise BackendError("Odoo returned a non-JSON response; check URL and database routing") from exc
                if not isinstance(result, dict):
                    raise BackendError("Unexpected Odoo API response")
                return result
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if read_only and attempt < 2:
                    await asyncio.sleep(0.25 * (2 ** attempt))
                    continue
                raise BackendError("Odoo is unavailable or timed out") from exc

    async def check(self, gemini):
        result = await self.call("capabilities")
        if result.get("api_version") != API_VERSION or not result.get("vector_ready"):
            raise BackendError("Odoo addon version or pgvector prerequisite is not ready")
        if (result.get("embedding_model"), result.get("dimensions")) != (gemini.embedding_model, gemini.dimensions):
            raise BackendError("Embedding settings differ from Odoo; align both settings and reindex documents")
        return result
