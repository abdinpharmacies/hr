"""SQL persistence for the independent FastRAG database, never the Odoo database."""

from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool


class StoreError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def digest(value):
    return sha256(value.encode()).hexdigest()


def vector_text(vector):
    return "[" + ",".join(map(str, vector)) + "]"


async def one(db, sql, params=()):
    return await (await db.execute(sql, params)).fetchone()


async def rows(db, sql, params=()):
    return await (await db.execute(sql, params)).fetchall()


RECORD = "id, source_id, title, text, metadata, public, archived, revision, indexed_revision, indexed_profile"
JOB = "j.id, j.record_id, j.revision, j.profile, j.status, j.attempts, j.error"
ATTACHMENT = "id, filename, caption, size"


class Store:
    def __init__(self, dsn):
        self.pool = AsyncConnectionPool(dsn, open=False, min_size=1, max_size=8, timeout=5,
                                        kwargs={"row_factory": dict_row, "connect_timeout": 5})

    async def migrate(self):
        async with self.pool.connection() as db:
            await db.execute(Path(__file__).with_name("pg_schema.sql").read_text(encoding="utf-8"))

    async def ready(self):
        async with self.pool.connection() as db:
            await db.execute("SELECT 'rag_jobs'::regclass, '[1]'::vector")

    async def add_key(self, collection, key_digest, permissions, public_only):
        async with self.pool.connection() as db:
            await db.execute("INSERT INTO rag_collections VALUES (%s) ON CONFLICT DO NOTHING", (collection,))
            await db.execute("INSERT INTO rag_keys (digest, collection, permissions, public_only) VALUES (%s,%s,%s,%s)",
                             (key_digest, collection, permissions, public_only))

    async def revoke_key(self, key_digest):
        async with self.pool.connection() as db:
            result = await db.execute("UPDATE rag_keys SET revoked=true WHERE digest=%s AND NOT revoked", (key_digest,))
            return bool(result.rowcount)

    async def get_key(self, key_digest):
        async with self.pool.connection() as db:
            return await one(db, """SELECT collection, permissions, public_only FROM rag_keys
                                      WHERE digest=%s AND NOT revoked""", (key_digest,))

    @asynccontextmanager
    async def replay(self, db, collection, operation, key, fingerprint):
        reply = {}
        if key is not None:
            await db.execute("""INSERT INTO rag_requests (collection, operation, key, fingerprint)
                                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                             (collection, operation, key, fingerprint))
            saved = await one(db, """SELECT fingerprint, response FROM rag_requests
                                    WHERE collection=%s AND operation=%s AND key=%s FOR UPDATE""",
                              (collection, operation, key))
            if saved["fingerprint"] != fingerprint:
                raise StoreError(409, "Idempotency key was used with a different payload")
            if saved["response"] is not None:
                reply["value"] = saved["response"]
                yield reply
                return
        yield reply
        if key is not None:
            await db.execute("""UPDATE rag_requests SET response=%s
                                WHERE collection=%s AND operation=%s AND key=%s""",
                             (Jsonb(reply["value"]), collection, operation, key))

    async def record(self, db, collection, rid, *, lock=False):
        rec = await one(db, f"SELECT {RECORD} FROM rag_records WHERE collection=%s AND id=%s"
                            + (" FOR UPDATE" if lock else ""), (collection, rid))
        if rec is None:
            raise StoreError(404, "Record not found")
        return rec

    async def list_records(self, collection, after, limit, source_id):
        async with self.pool.connection() as db:
            return await rows(db, """SELECT id, source_id, title, metadata, public, archived, revision,
                                      indexed_revision, indexed_profile FROM rag_records WHERE collection=%s
                                      AND (%s::uuid IS NULL OR id>%s)
                                      AND (%s::text IS NULL OR source_id=%s) ORDER BY id LIMIT %s""",
                              (collection, after, after, source_id, source_id, limit))

    async def get_record(self, collection, rid):
        async with self.pool.connection() as db:
            rec = await self.record(db, collection, rid, lock=True)
            rec["attachments"] = await rows(db, f"SELECT {ATTACHMENT} FROM rag_files WHERE record_id=%s ORDER BY id",
                                            (rid,))
            return rec

    async def create(self, db, collection, data):
        rec = await one(db, f"""INSERT INTO rag_records (id,collection,source_id,title,text,metadata,public)
                                VALUES (%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (collection,source_id) DO NOTHING RETURNING {RECORD}""",
                        (uuid4(), collection, data["source_id"], data["title"], data["text"],
                         Jsonb(data["metadata"]), data["public"]))
        if rec is None:
            raise StoreError(409, "Source ID already exists")
        return rec

    async def update(self, db, collection, rid, changes):
        rec = await self.record(db, collection, rid, lock=True)
        updated = rec | changes
        reindex = int(any(rec[k] != updated[k] for k in ("title", "text")))
        return await one(db, f"""UPDATE rag_records SET title=%s,text=%s,metadata=%s,public=%s,archived=%s,
                                revision=revision+%s WHERE id=%s RETURNING {RECORD}""",
                         (updated["title"], updated["text"], Jsonb(updated["metadata"]), updated["public"],
                          updated["archived"], reindex, rid))

    async def add_file(self, db, collection, rid, filename, caption, content):
        rec = await self.record(db, collection, rid, lock=True)
        if rec["archived"]:
            raise StoreError(409, "Record is archived")
        usage = await one(db, "SELECT count(*) AS count, coalesce(sum(size),0) AS size FROM rag_files WHERE record_id=%s",
                          (rid,))
        if usage["count"] >= 50 or usage["size"] + len(content) > 100 * 1024 * 1024:
            raise StoreError(413, "Record attachment limit exceeded")
        result = await one(db, f"""INSERT INTO rag_files VALUES (%s,%s,%s,%s,%s,%s) RETURNING {ATTACHMENT}""",
                           (uuid4(), rid, filename, caption, len(content), content))
        await db.execute("UPDATE rag_records SET revision=revision+1 WHERE id=%s", (rid,))
        return result

    async def get_file(self, collection, rid, fid):
        async with self.pool.connection() as db:
            result = await one(db, """SELECT f.filename, f.content FROM rag_files f JOIN rag_records r
                                     ON r.id=f.record_id WHERE r.collection=%s AND r.id=%s AND f.id=%s""",
                               (collection, rid, fid))
            if result is None:
                raise StoreError(404, "Attachment not found")
            return result

    async def remove_file(self, db, collection, rid, fid):
        await self.record(db, collection, rid, lock=True)
        result = await db.execute("DELETE FROM rag_files WHERE record_id=%s AND id=%s", (rid, fid))
        if not result.rowcount:
            raise StoreError(404, "Attachment not found")
        await db.execute("UPDATE rag_records SET revision=revision+1 WHERE id=%s", (rid,))

    async def enqueue(self, db, collection, rid, profile):
        rec = await self.record(db, collection, rid, lock=True)
        if rec["archived"]:
            raise StoreError(409, "Record is archived")
        rebuild = rec["indexed_profile"] != profile or rec["indexed_revision"] != rec["revision"]
        return await one(db, f"""INSERT INTO rag_jobs AS j (id,record_id,revision,profile) VALUES (%s,%s,%s,%s)
                                ON CONFLICT (record_id,revision,profile) DO UPDATE SET
                                status='queued', attempts=0, error=NULL, available_at=now()
                                WHERE j.status='failed' OR (j.status='succeeded' AND %s)
                                RETURNING {JOB}""", (uuid4(), rid, rec["revision"], profile, rebuild)) or await one(
            db, f"SELECT {JOB} FROM rag_jobs j WHERE record_id=%s AND revision=%s AND profile=%s",
            (rid, rec["revision"], profile))

    async def get_job(self, collection, jid):
        async with self.pool.connection() as db:
            job = await one(db, f"""SELECT {JOB} FROM rag_jobs j JOIN rag_records r ON r.id=j.record_id
                                    WHERE j.id=%s AND r.collection=%s""", (jid, collection))
            if job is None:
                raise StoreError(404, "Job not found")
            return job

    async def claim(self, profile):
        async with self.pool.connection() as db:
            await db.execute("""UPDATE rag_jobs SET status='failed', error='Indexing lease expired',
                                token=NULL, lease_until=NULL WHERE profile=%s AND status='running'
                                AND lease_until<=now() AND attempts>=3""", (profile,))
            return await one(db, """WITH next AS (
                                     SELECT id FROM rag_jobs WHERE profile=%s AND
                                     ((status='queued' AND available_at<=now()) OR
                                      (status='running' AND lease_until<=now()))
                                     ORDER BY available_at,id LIMIT 1 FOR UPDATE SKIP LOCKED
                                   ) UPDATE rag_jobs j SET status='running', attempts=attempts+1,
                                     token=%s, lease_until=now()+interval '60 seconds', error=NULL
                                     FROM next WHERE j.id=next.id RETURNING j.*""", (profile, uuid4()))

    async def renew(self, job):
        async with self.pool.connection() as db:
            result = await db.execute("""UPDATE rag_jobs SET lease_until=now()+interval '60 seconds'
                                         WHERE id=%s AND token=%s AND lease_until>now()""", (job["id"], job["token"]))
            return bool(result.rowcount)

    async def finish(self, job, entries=None, error=None, retry=False):
        rid = job["record_id"]
        async with self.pool.connection() as db:
            rec = await one(db, "SELECT revision, archived FROM rag_records WHERE id=%s FOR UPDATE", (rid,))
            active = await one(db, """SELECT attempts FROM rag_jobs WHERE id=%s AND token=%s
                                      AND lease_until>now() FOR UPDATE""", (job["id"], job["token"]))
            if not active:
                return
            status = "failed"
            if rec["revision"] != job["revision"] or rec["archived"]:
                error = "Record revision changed or was archived"
            elif entries is not None:
                await db.execute("DELETE FROM rag_chunks WHERE record_id=%s", (rid,))
                async with db.cursor() as cur:
                    await cur.executemany("INSERT INTO rag_chunks VALUES (%s,%s,%s,%s,%s::vector)",
                                          [(rid, i, fid, text, vector_text(vec))
                                           for i, (fid, text, vec) in enumerate(entries)])
                await db.execute("UPDATE rag_records SET indexed_revision=%s,indexed_profile=%s WHERE id=%s",
                                 (job["revision"], job["profile"], rid))
                status = "succeeded"
            elif retry and active["attempts"] < 3:
                status = "queued"
            await db.execute("""UPDATE rag_jobs SET status=%s,error=%s,token=NULL,lease_until=NULL,
                                available_at=now()+%s*interval '1 second' WHERE id=%s""",
                             (status, error, 2 ** active["attempts"], job["id"]))

    async def snapshot(self, job):
        rid = job["record_id"]
        async with self.pool.connection() as db:
            rec = await one(db, """SELECT title,text,collection FROM rag_records WHERE id=%s
                                   AND revision=%s AND NOT archived FOR UPDATE""", (rid, job["revision"]))
            if rec is None:
                raise ValueError("Record revision changed or was archived")
            files = await rows(db, "SELECT id,filename,caption,content FROM rag_files WHERE record_id=%s ORDER BY id",
                               (rid,))
        return rec, files

    async def search(self, collection, public_only, profile, vector, limit, threshold):
        async with self.pool.connection() as db:
            return await rows(db, """WITH visible AS MATERIALIZED (
                                      SELECT c.record_id,c.file_id,c.chunk_index,c.content,c.embedding,
                                             r.title,r.source_id,r.revision
                                      FROM rag_records r JOIN rag_chunks c ON c.record_id=r.id
                                      WHERE r.collection=%s AND NOT r.archived AND (NOT %s OR r.public)
                                      AND r.indexed_revision=r.revision AND r.indexed_profile=%s
                                    ), scored AS (
                                      SELECT record_id,file_id,chunk_index,content,title,source_id,revision,
                                             1-(embedding <=> %s::vector) AS score FROM visible
                                    ) SELECT * FROM scored WHERE score >= %s
                                    ORDER BY score DESC, record_id, chunk_index LIMIT %s""",
                              (collection, public_only, profile, vector_text(vector), threshold, limit))

    async def still_visible(self, collection, public_only, profile, matches):
        ids = list({m["record_id"] for m in matches})
        async with self.pool.connection() as db:
            current = await rows(db, """SELECT id,revision FROM rag_records WHERE id=ANY(%s)
                                        AND collection=%s AND NOT archived AND (NOT %s OR public)
                                        AND indexed_revision=revision AND indexed_profile=%s""",
                                 (ids, collection, public_only, profile))
        revisions = {r["id"]: r["revision"] for r in current}
        return all(revisions.get(m["record_id"]) == m["revision"] for m in matches)

    async def prune(self):
        async with self.pool.connection() as db:
            await db.execute("""DELETE FROM rag_requests WHERE (collection,operation,key) IN (
                                  SELECT collection,operation,key FROM rag_requests
                                  WHERE created_at < now()-interval '24 hours' LIMIT 1000 FOR UPDATE SKIP LOCKED
                                )""")
