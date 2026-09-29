import base64
import csv
import hashlib
import json
import os
import zipfile
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import requests
from ijson.common import JSONError
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config

from ..services.datasets import members, records
from ..services.providers import ProviderFailure, adapter, digest, gtin, match, normalized, strings
from .enrichment_provider import MANAGER


class EnrichmentDataset(models.Model):
    _name = "ab_seo_dataset"
    _description = "Enrichment Dataset Import"
    _order = "id desc"

    name = fields.Char(compute="_compute_name", store=True)
    provider_id = fields.Many2one("ab.seo.assistant", required=True, index=True, ondelete="restrict")
    source_version = fields.Char(required=True, default=lambda self: fields.Date.to_string(fields.Date.today()))
    url = fields.Char()
    filename = fields.Char(required=True, default="dataset.json")
    upload = fields.Binary(attachment=True, groups=MANAGER)
    state = fields.Selection([(v, v.title()) for v in ("draft", "queued", "download", "normalize", "import", "done", "failed")], default="draft", required=True, index=True)
    checksum = fields.Char(readonly=True, index=True)
    expected_checksum = fields.Char()
    etag = fields.Char(readonly=True)
    last_modified = fields.Char(readonly=True)
    downloaded_at = fields.Datetime(readonly=True)
    last_successful_sync = fields.Datetime(readonly=True)
    record_count = fields.Integer(readonly=True)
    failed_record_count = fields.Integer(readonly=True)
    imported_count = fields.Integer(readonly=True)
    download_bytes = fields.Float(readonly=True, digits=(20, 0))
    import_offset = fields.Float(readonly=True, digits=(20, 0))
    last_error = fields.Text(readonly=True)
    json_prefix = fields.Char()
    max_download_mb = fields.Integer(default=4096)
    next_attempt_at = fields.Datetime(index=True)
    attempts = fields.Integer(readonly=True)
    duplicate_of_id = fields.Many2one("ab_seo_dataset", readonly=True, ondelete="restrict")
    manual_verified_by = fields.Many2one("res.users", readonly=True)
    manual_verified_at = fields.Datetime(readonly=True)
    verification_note = fields.Text()
    incremental = fields.Boolean(default=True)

    @api.depends("provider_id.name", "source_version")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s / %s" % (rec.provider_id.name, rec.source_version or "")

    def _directory(self):
        root = Path(config.filestore(self.env.cr.dbname)) / "seo_datasets" / str(self.id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def action_validate_dataset(self):
        self.provider_id._require_enrichment_manager()
        for rec in self:
            if not rec.url and not rec.upload:
                raise UserError(_("Upload a dataset or configure a download URL."))
            if rec.url:
                parsed = urlsplit(rec.url)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query:
                    raise UserError(_("Dataset URLs must use HTTPS without embedded credentials or query tokens. Upload licensed files separately."))
            if not rec.source_version or not rec.filename:
                raise UserError(_("Dataset revision and filename are required."))
            if not rec.provider_id._allowed_for_commercial():
                raise UserError(_("Record the source license review and any required commercial permission before import."))
        return True

    def action_queue_import(self):
        self.action_validate_dataset()
        for rec in self:
            if rec.state in ("download", "normalize", "import"):
                continue
            rec.write({"state": "queued", "last_error": False, "next_attempt_at": False, "attempts": 0})
        return True

    def action_verify_manual(self):
        self.provider_id._require_enrichment_manager()
        for rec in self:
            if not rec.verification_note or not rec.url:
                raise UserError(_("Record the official evidence URL and verification note."))
            rec.write({"manual_verified_by": self.env.user.id, "manual_verified_at": fields.Datetime.now()})
        return True

    def action_rebuild_index(self):
        self.provider_id._require_enrichment_manager()
        for rec in self:
            if not (rec._directory() / "normalized.jsonl").exists():
                raise UserError(_("The retained normalized dataset file is unavailable."))
            rec.write({"state": "import", "import_offset": 0, "imported_count": 0, "last_error": False})
        return True

    def action_resume(self):
        self.provider_id._require_enrichment_manager()
        for rec in self.filtered(lambda r: r.state == "failed"):
            root = rec._directory()
            state = "import" if (root / "normalized.jsonl").exists() else "normalize" if rec.checksum else "queued"
            rec.write({"state": state, "last_error": False, "attempts": 0, "next_attempt_at": False})
        return True

    @api.model
    def _cron_sync_datasets(self):
        now = fields.Datetime.now()
        providers = self.env["ab.seo.assistant"].search(fields.Domain("sync_interval_days", ">", 0) & fields.Domain("next_sync_at", "<=", now))
        for provider in providers:
            if provider.try_lock_for_update(allow_referencing=True) and not self.search_count(fields.Domain("provider_id", "=", provider.id) & fields.Domain("state", "in", ("queued", "download", "normalize", "import"))):
                try:
                    provider.action_sync_dataset()
                except (ProviderFailure, UserError) as error:
                    provider._record_failure(error if isinstance(error, ProviderFailure) else ProviderFailure("dataset_configuration_required"))
                provider.next_sync_at = now + timedelta(days=provider.sync_interval_days)
        pending = self.search(fields.Domain("state", "in", ("queued", "download", "normalize", "import")) & (fields.Domain("next_attempt_at", "=", False) | fields.Domain("next_attempt_at", "<=", now)), limit=5, order="id")
        for dataset in pending:
            if not dataset.try_lock_for_update():
                continue
            try:
                dataset._step()
            except (ProviderFailure, requests.RequestException, OSError, ValueError, EOFError, zipfile.BadZipFile, etree.XMLSyntaxError, JSONError, csv.Error, UserError) as error:
                code = error.code if isinstance(error, ProviderFailure) else type(error).__name__
                count = dataset.attempts + 1
                dataset.write({"last_error": code, "attempts": count, "state": "failed" if count >= 3 else dataset.state,
                               "next_attempt_at": now + timedelta(seconds=min(3600, 60 * 2 ** count))})
            if self.env.context.get("cron_id") and not self.env["ir.cron"]._commit_progress(1):
                break
        return True

    def _step(self):
        self.ensure_one()
        if self.state == "queued":
            self.action_validate_dataset()
            self.state = "download"
        if self.state == "download":
            self._download_chunk()
        elif self.state == "normalize":
            self._normalize_file()
        elif self.state == "import":
            self._import_chunk()

    def _download_chunk(self):
        self.ensure_one()
        root = self._directory()
        path = root / "raw"
        cap = max(self.max_download_mb, 1) * 1024 * 1024
        if self.upload:
            data = base64.b64decode(self.upload)
            if len(data) > cap:
                raise ProviderFailure("download_size_limit")
            path.write_bytes(data)
            self._finish_download(path)
            return
        offset = path.stat().st_size if path.exists() else 0
        headers = {"User-Agent": "AbdinSEO/19.0 (bulk dataset import)", "Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = "bytes=%s-%s" % (offset, offset + 8 * 1024 * 1024 - 1)
            if self.etag or self.last_modified:
                headers["If-Range"] = self.etag or self.last_modified
        else:
            previous = self.search(fields.Domain("provider_id", "=", self.provider_id.id) & fields.Domain("url", "=", self.url) & fields.Domain("state", "=", "done"), limit=1)
            if previous.etag:
                headers["If-None-Match"] = previous.etag
            if previous.last_modified:
                headers["If-Modified-Since"] = previous.last_modified
        with requests.get(self.url, headers=headers, stream=True, timeout=(5, 30), allow_redirects=False) as response:
            if response.status_code == 416 and offset:
                total = response.headers.get("Content-Range", "").split("/")[-1]
                if total.isdigit() and int(total) == offset:
                    self._finish_download(path)
                    return
            if response.status_code == 304:
                self.write({"state": "done", "duplicate_of_id": previous.id, "checksum": previous.checksum, "last_successful_sync": fields.Datetime.now()})
                return
            if response.status_code not in (200, 206):
                raise ProviderFailure("dataset_http_%s" % response.status_code, response.status_code)
            if offset and response.status_code == 200:
                offset = 0
            total_header = response.headers.get("Content-Range", "").split("/")[-1]
            total = int(total_header) if total_header.isdigit() else offset + int(response.headers.get("Content-Length") or 0)
            if total > cap:
                raise ProviderFailure("download_size_limit")
            supports_range = response.status_code == 206 or response.headers.get("Accept-Ranges") == "bytes"
            downloaded = offset
            finished = True
            with path.open("ab" if offset else "wb") as output:
                for chunk in response.iter_content(256 * 1024):
                    downloaded += len(chunk)
                    if downloaded > cap:
                        raise ProviderFailure("download_size_limit")
                    output.write(chunk)
                    if supports_range and downloaded - offset >= 8 * 1024 * 1024 and (not total or downloaded < total):
                        finished = False
                        break
            self.write({"download_bytes": downloaded, "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")})
            if finished and (not total or downloaded >= total):
                self._finish_download(path)

    def _finish_download(self, path):
        checksum = hashlib.sha256()
        legacy_checksum = hashlib.md5(usedforsecurity=False)
        with path.open("rb") as raw:
            for block in iter(lambda: raw.read(1024 * 1024), b""):
                checksum.update(block)
                legacy_checksum.update(block)
        value = checksum.hexdigest()
        expected = (self.expected_checksum or "").lower().strip()
        supplied = expected.split(":", 1)[-1]
        actual = legacy_checksum.hexdigest() if expected.startswith("md5:") or len(supplied) == 32 else value
        if supplied and supplied != actual:
            raise ProviderFailure("checksum_mismatch")
        duplicate = self.search(fields.Domain("provider_id", "=", self.provider_id.id) & fields.Domain("checksum", "=", value) & fields.Domain("state", "=", "done"), limit=1)
        self.write({"checksum": value, "downloaded_at": fields.Datetime.now(), "download_bytes": path.stat().st_size,
                    "state": "done" if duplicate else "normalize", "duplicate_of_id": duplicate.id})

    def _normalize_file(self):
        root = self._directory()
        parser = adapter(self.provider_id.provider)
        good, bad = 0, 0
        with (root / "normalized.pending").open("wb") as output:
            with members(root / "raw", self.filename) as files:
                for filename, handle in files:
                    for row in records(handle, filename, self.provider_id.provider, self.json_prefix or ""):
                        try:
                            item = parser.normalize(row)
                            item["source_version"] = self.source_version
                            item["source_url"] = self.url or self.provider_id.official_url
                            item["checksum"] = self.checksum
                            item["dataset_id"] = self.id
                            item["retrieved_at"] = fields.Datetime.to_string(self.downloaded_at or fields.Datetime.now())
                            item["active"] = row.get("_source_active", True)
                            output.write(json.dumps(item, ensure_ascii=False).encode() + b"\n")
                            good += 1
                        except ProviderFailure:
                            bad += 1
        if not good:
            raise ProviderFailure("empty_dataset")
        os.replace(root / "normalized.pending", root / "normalized.jsonl")
        self.write({"record_count": good, "failed_record_count": bad, "state": "import", "import_offset": 0})

    def _import_chunk(self, limit=500):
        values = []
        with (self._directory() / "normalized.jsonl").open("rb") as source:
            source.seek(int(self.import_offset))
            for _index in range(limit):
                line = source.readline()
                if not line:
                    break
                values.append(json.loads(line))
            offset = source.tell()
            done = not source.read(1)
        self.env["ab_seo_source_record"]._upsert(self, values)
        self.write({"import_offset": offset, "imported_count": self.imported_count + len(values)})
        if done:
            if not self.incremental:
                self.env["ab_seo_source_record"].search(fields.Domain("provider_id", "=", self.provider_id.id) & fields.Domain("dataset_id", "<", self.id)).write({"active": False})
            self.write({"state": "done", "last_successful_sync": fields.Datetime.now(), "last_error": False})
            self.provider_id.write({"last_successful_sync": fields.Datetime.now(), "index_revision": self.provider_id.index_revision + 1})

    def unlink(self):
        raise UserError(_("Retained datasets cannot be deleted through enrichment actions."))


class SourceRecord(models.Model):
    _name = "ab_seo_source_record"
    _description = "Local Enrichment Source Record"
    _rec_name = "name"

    provider_id = fields.Many2one("ab.seo.assistant", required=True, index=True, ondelete="restrict")
    dataset_id = fields.Many2one("ab_seo_dataset", required=True, index=True, ondelete="restrict")
    source_id = fields.Char(required=True, index=True)
    name = fields.Char(index=True)
    normalized_name = fields.Char(index=True)
    name_prefix = fields.Char(index=True)
    manufacturer = fields.Char(index=True)
    strength = fields.Char()
    dosage_form = fields.Char()
    payload = fields.Json(required=True)
    payload_hash = fields.Char(required=True)
    identifier_ids = fields.One2many("ab_seo_source_identifier", "record_id")
    active = fields.Boolean(default=True, index=True)

    _unique_source = models.Constraint("UNIQUE(provider_id, source_id)", "Source identifiers must be unique within a provider.")

    @api.model
    def _upsert(self, dataset, items):
        unique = {item["source_id"]: item for item in items}
        existing = {r.source_id: r for r in self.with_context(active_test=False).search(fields.Domain("provider_id", "=", dataset.provider_id.id) & fields.Domain("source_id", "in", list(unique)))}
        new_values = []
        identifiers = self.env["ab_seo_source_identifier"]
        for source_id, item in unique.items():
            fact = item["facts"]
            name = normalized(fact.get("name"))
            vals = {"provider_id": dataset.provider_id.id, "dataset_id": dataset.id, "source_id": source_id, "name": fact.get("name"),
                    "normalized_name": name, "name_prefix": name[:4], "manufacturer": normalized(fact.get("manufacturer")),
                    "strength": normalized(fact.get("strength")), "dosage_form": normalized(fact.get("dosage_form")),
                    "payload": item, "payload_hash": digest(item), "active": item.get("active", True)}
            old = existing.get(source_id)
            if old:
                if old.dataset_id.id > dataset.id:
                    continue
                if old.payload_hash != vals["payload_hash"]:
                    old.write(vals)
                    old.identifier_ids.unlink()
                    identifiers.create(old._identifier_values(item))
            else:
                new_values.append(vals)
        if new_values:
            created = self.create(new_values)
            identifiers.create([v for row in created for v in row._identifier_values(row.payload)])

    def _identifier_values(self, item):
        return [{"provider_id": self.provider_id.id, "record_id": self.id, "kind": kind, "value": value}
                for kind, values in item.get("identifiers", {}).items() for value in set(strings(values)) if value]

    @api.model
    def _lookup(self, provider, identity):
        base = fields.Domain("provider_id", "=", provider.id) & fields.Domain("dataset_id.state", "=", "done")
        identifiers = self.env["ab_seo_source_identifier"]
        for kind in ("source_id", "gtin", "ndc", "rxcui", "registration", "cas", "inchi", "ec", "inci"):
            values = strings(identity.get(kind))
            if kind == "source_id":
                values = strings((identity.get("source_ids") or {}).get(provider.provider) or identity.get("source_id"))
            if kind == "gtin":
                values = [gtin(v) for v in values if gtin(v)]
            if not values:
                continue
            rows = identifiers.search(fields.Domain("provider_id", "=", provider.id) & fields.Domain("kind", "=", kind) & fields.Domain("value", "in", values) & fields.Domain("record_id.active", "=", True) & fields.Domain("record_id.dataset_id.state", "=", "done"), limit=30).mapped("record_id")
            if rows:
                return rows.mapped("payload")
        name = normalized(identity.get("name"))
        if not name:
            return []
        rows = self.search(base & fields.Domain("normalized_name", "=", name), limit=30)
        if not rows:
            rows = self.search(base & fields.Domain("name_prefix", "=", name[:4]), limit=100)
        matches = [(match(identity, r.payload)["match_score"], r.payload) for r in rows]
        return [payload for score, payload in sorted(matches, key=lambda v: v[0], reverse=True) if score >= .8][:10]


class SourceIdentifier(models.Model):
    _name = "ab_seo_source_identifier"
    _description = "Indexed Source Identifier"

    provider_id = fields.Many2one("ab.seo.assistant", required=True, index=True, ondelete="cascade")
    record_id = fields.Many2one("ab_seo_source_record", required=True, index=True, ondelete="cascade")
    kind = fields.Char(required=True, index=True)
    value = fields.Char(required=True, index=True)

    _lookup_index = models.Index("(provider_id, kind, value)")
    _unique_identifier = models.Constraint("UNIQUE(record_id, kind, value)", "Source identifiers cannot be duplicated.")
