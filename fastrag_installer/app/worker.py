import asyncio
import base64
from contextlib import suppress
import logging

from .documents import extract_text, chunks

log = logging.getLogger(__name__)


async def process_job(job, engine):
    if job["kind"] == "ask":
        result = await engine.ask_conversation(job) if job.get("conversation") else await engine.ask(job["question"])
        return await engine.backend.call("complete_answer", job_id=job["id"], token=job["token"], **result)
    if job["kind"] != "index":
        raise ValueError("Unknown job type")
    sections = [(None, job.get("record_text", ""))]
    files = job.get("files", [])
    if len(files) > 50:
        raise ValueError("Too many files")
    total_bytes = 0
    for file in files:
        text = file.get("description") or ""
        if file.get("extractable"):
            result = await engine.backend.call("job_file", job_id=job["id"], token=job["token"], file_id=file["id"])
            raw = base64.b64decode(result["content_base64"], validate=True)
            total_bytes += len(raw)
            if len(raw) > engine.settings.rag.max_upload_mb * 1024 * 1024 or total_bytes > 100 * 1024 * 1024:
                raise ValueError("Document exceeds upload limit")
            extracted = await asyncio.to_thread(extract_text, file["filename"], raw, engine.settings.rag.max_text_chars)
            text += "\n" + extracted
        if text.strip():
            sections.append((file["id"], f"File: {file['filename']}\n{text}"))
    if sum(len(text) for _, text in sections) > engine.settings.rag.max_text_chars:
        raise ValueError("Record text exceeds limit")
    entries = []
    async with engine.gate:
        for file_id, text in sections:
            if not text.strip():
                continue
            pieces = chunks(text, engine.settings.rag.chunk_chars, engine.settings.rag.overlap_chars, engine.settings.rag.max_chunks)
            for piece in pieces:
                if len(entries) >= engine.settings.rag.max_chunks:
                    raise ValueError("Record chunk count exceeds limit")
                entries.append({"index": len(entries), "file_id": file_id, "content": piece,
                                "embedding": await engine.provider.embed(piece)})
    if not entries:
        raise ValueError("Record has no indexable text")
    return await engine.backend.call("complete_index", job_id=job["id"], token=job["token"], chunks=entries,
                                     **engine.profile())


async def execute_claim(job, engine):
    task = asyncio.create_task(process_job(job, engine))
    try:
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=30)
            if not done:
                result = await engine.backend.call("renew_job", job_id=job["id"], token=job["token"])
                if not result.get("renewed"):
                    raise RuntimeError("Job lease was lost")
        return await task
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task


async def run_worker(engine):
    while True:
        job = None
        try:
            await engine.backend.check(engine.settings.gemini)
            result = await engine.backend.call("claim_job", **engine.profile())
            job = result.get("job")
            if job:
                await execute_claim(job, engine)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Do not log exception payloads that may contain provider URLs/keys.
            log.warning("RAG worker operation failed (%s)", type(exc).__name__)
            if job:
                with suppress(Exception):
                    await engine.backend.call("fail_job", job_id=job["id"], token=job["token"],
                                              error=f"Processing failed ({type(exc).__name__}); inspect configuration or document")
        await asyncio.sleep(engine.settings.worker.poll_seconds)
