import base64
import binascii
import hashlib
import io
import re
import uuid
from copy import deepcopy
from urllib.parse import urlsplit

from PIL import Image

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


BLOCK_TYPES = {'hero', 'heading', 'text', 'image', 'button', 'divider'}
FONTS = {'system', 'arabic', 'georgia', 'monospace'}
ALIGNMENTS = {'start', 'center', 'end'}
HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
STYLE_KEYS = {'color', 'background', 'font', 'size', 'padding', 'radius', 'align', 'border_color', 'border_width', 'mobile_size', 'visibility', 'weight', 'italic'}
TEXT_KEYS = {'title', 'body', 'label', 'alt'}


def validate_website(website):
    website.check_access('read')
    if not website.env.su and website.company_id not in website.env.companies:
        raise AccessError(_('Choose a website in your allowed companies.'))


def validate_style(style):
    if not isinstance(style, dict) or set(style) - STYLE_KEYS:
        raise ValidationError(_('This design style is not supported.'))
    for key in ('color', 'background', 'border_color'):
        if key in style and (not isinstance(style[key], str) or not HEX_COLOR.fullmatch(style[key])):
            raise ValidationError(_('Use six-digit hex colors for content styles.'))
    if 'font' in style and (not isinstance(style['font'], str) or style['font'] not in FONTS):
        raise ValidationError(_('This font is not supported.'))
    if 'align' in style and (not isinstance(style['align'], str) or style['align'] not in ALIGNMENTS):
        raise ValidationError(_('This alignment is not supported.'))
    for key, options in (('visibility', {'all', 'desktop', 'mobile'}), ('weight', {'normal', 'bold'})):
        if key in style and (not isinstance(style[key], str) or style[key] not in options):
            raise ValidationError(_('This design style is not supported.'))
    if 'italic' in style and type(style['italic']) is not bool:
        raise ValidationError(_('This design style is not supported.'))
    for key, lower, upper in (('size', 12, 72), ('padding', 0, 96), ('radius', 0, 48), ('border_width', 0, 8), ('mobile_size', 12, 48)):
        if key in style and (type(style[key]) is not int or not lower <= style[key] <= upper):
            raise ValidationError(_('A design value is outside the supported range.'))


def validate_url(value, image=False):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValidationError(_('This content link is invalid.'))
    if not value:
        return
    if '\\' in value or any(ord(char) < 32 for char in value):
        raise ValidationError(_('This content link is invalid.'))
    try:
        parts = urlsplit(value)
    except ValueError:
        raise ValidationError(_('This content link is invalid.')) from None
    internal = value.startswith('/') and not value.startswith('//') and not parts.netloc
    external = parts.scheme == 'https' and bool(parts.netloc) and not parts.username and not parts.password
    if not (internal or external) or (image and internal and not value.startswith('/web/image/')):
        raise ValidationError(_('Use an HTTPS link or an allowed site path.'))


def validate_blocks(blocks, allow_template=False):
    if not isinstance(blocks, list) or len(blocks) > 80:
        raise ValidationError(_('A page can contain up to 80 blocks.'))
    seen = set()
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get('id'), str):
            raise ValidationError(_('A content block is invalid.'))
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}', block['id']) or block['id'] in seen:
            raise ValidationError(_('Each content block needs a unique identifier.'))
        seen.add(block['id'])
        kind = block.get('type')
        if kind == 'template' and allow_template:
            if set(block) != {'id', 'type', 'template_id'} or type(block['template_id']) is not int:
                raise ValidationError(_('The reusable block reference is invalid.'))
            continue
        if not isinstance(kind, str) or kind not in BLOCK_TYPES or set(block) - ({'id', 'type', 'style', 'url'} | TEXT_KEYS):
            raise ValidationError(_('This block type is not supported.'))
        validate_style(block.get('style', {}))
        for key in TEXT_KEYS:
            if key in block and (not isinstance(block[key], str) or len(block[key]) > 4000):
                raise ValidationError(_('Block text is too long.'))
        if 'url' in block:
            validate_url(block['url'], image=kind == 'image')


class EditorDocument(models.Model):
    _name = 'ab_ecommerce_editor_document'
    _description = 'eCommerce Editor Document'
    _order = 'write_date desc, id desc'

    name = fields.Char(required=True, translate=False)
    kind = fields.Selection([('page', 'Page'), ('blog', 'Blog post')], required=True, default='page')
    website_id = fields.Many2one('website', required=True, default=lambda self: self.env['website'].search(fields.Domain('company_id', 'in', self.env.companies.ids), limit=1))
    company_id = fields.Many2one(related='website_id.company_id', store=True)
    slug = fields.Char(required=True)
    category = fields.Char()
    image_url = fields.Char()
    title_en = fields.Char(required=True)
    title_ar = fields.Char()
    summary_en = fields.Text()
    summary_ar = fields.Text()
    blocks_en = fields.Json(default=list)
    blocks_ar = fields.Json(default=list)
    design_tokens = fields.Json(default=dict)
    web_overrides = fields.Json(default=dict)
    flutter_overrides = fields.Json(default=dict)
    seo_title_en = fields.Char()
    seo_title_ar = fields.Char()
    seo_description_en = fields.Text()
    seo_description_ar = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'), ('review', 'In review'),
        ('scheduled', 'Scheduled'), ('published', 'Published'),
    ], default='draft', required=True, readonly=True)
    scheduled_at = fields.Datetime(readonly=True)
    published_at = fields.Datetime(readonly=True)
    version = fields.Integer(default=0, readonly=True)
    published_revision_id = fields.Many2one('ab_ecommerce_editor_revision', readonly=True, copy=False)
    review_revision_id = fields.Many2one('ab_ecommerce_editor_revision', readonly=True, copy=False)
    scheduled_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    revision_ids = fields.One2many('ab_ecommerce_editor_revision', 'document_id', readonly=True)
    active = fields.Boolean(default=True)
    draft_token = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, copy=False)

    _unique_route = models.Constraint(
        'UNIQUE(website_id, kind, slug)',
        'This URL is already used on this website.',
    )

    @api.constrains('slug', 'blocks_en', 'blocks_ar', 'design_tokens', 'web_overrides', 'flutter_overrides', 'image_url')
    def _check_content(self):
        for document in self:
            if not SLUG.fullmatch(document.slug or ''):
                raise ValidationError(_('Use lowercase letters, numbers, and hyphens for the URL.'))
            validate_blocks(document.blocks_en or [], allow_template=True)
            validate_blocks(document.blocks_ar or [], allow_template=True)
            for value in (document.design_tokens, document.web_overrides, document.flutter_overrides):
                validate_style(value or {})
            validate_url(document.image_url or '', image=True)

    @api.model_create_multi
    def create(self, vals_list):
        forbidden = {'state', 'scheduled_at', 'published_at', 'version', 'published_revision_id', 'revision_ids', 'review_revision_id', 'scheduled_by_id', 'draft_token'}
        if any(forbidden.intersection(values) for values in vals_list):
            raise AccessError(_('Publishing fields can only change through editor actions.'))
        records = super().create(vals_list)
        for website in records.website_id:
            validate_website(website)
        return records

    def write(self, values):
        if 'website_id' in values:
            validate_website(self.env['website'].browse(values['website_id']))
        protected = {'state', 'scheduled_at', 'published_at', 'version', 'published_revision_id', 'revision_ids', 'review_revision_id', 'scheduled_by_id', 'draft_token'}
        if protected.intersection(values):
            raise AccessError(_('Publishing fields can only change through editor actions.'))
        if set(values) - {'active'}:
            if any(document.state in ('review', 'scheduled') for document in self):
                raise ValidationError(_('Return this content to draft before editing.'))
        for document in self:
            if document.version and any(
                key in values and values[key] != (document[key].id if key == 'website_id' else document[key])
                for key in ('website_id', 'kind', 'slug')
            ):
                raise ValidationError(_('Create a duplicate to change the website or URL of versioned content.'))
            if 'active' in values and (document.published_revision_id or document.state == 'scheduled'):
                document._require_role('publisher')
        if set(values) - {'active'} and any(document.state == 'published' for document in self):
            values = {**values, 'state': 'draft'}
        values = {**values, 'draft_token': str(uuid.uuid4())}
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Archive content instead of deleting it.'))

    def _require_role(self, role):
        group = f'ab_ecommerce_editor.group_editor_{role}'
        if not self.env.user.has_group(group) and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('You do not have permission for this editor action.'))
        self.check_access('write')
        locked = self.try_lock_for_update(allow_referencing=True)
        if len(locked) != len(self):
            raise ValidationError(_('This document is being changed by another editor. Try again.'))
        self.invalidate_recordset()

    def save_draft(self, values, expected_token):
        self.ensure_one()
        self._require_role('editor')
        if self.draft_token != expected_token:
            raise ValidationError(_('This draft changed in another session. Reload it before saving.'))
        allowed = {
            'name', 'kind', 'website_id', 'slug', 'category', 'image_url', 'title_en', 'title_ar',
            'summary_en', 'summary_ar', 'blocks_en', 'blocks_ar', 'design_tokens', 'web_overrides',
            'flutter_overrides', 'seo_title_en', 'seo_title_ar', 'seo_description_en', 'seo_description_ar',
        }
        if not isinstance(values, dict) or set(values) - allowed:
            raise AccessError(_('Only draft content can be saved from the editor.'))
        self.write(values)
        return {'write_date': fields.Datetime.to_string(self.write_date), 'state': self.state, 'draft_token': self.draft_token}

    def upload_image(self, filename, data):
        self.ensure_one()
        self._require_role('editor')
        if self.state in ('review', 'scheduled'):
            raise ValidationError(_('Return this content to draft before editing.'))
        if not isinstance(data, str) or len(data) > 7_000_000:
            raise ValidationError(_('Choose an image smaller than 5 MB.'))
        try:
            binary = base64.b64decode(data, validate=True)
            if len(binary) > 5 * 1024 * 1024:
                raise ValueError()
            with Image.open(io.BytesIO(binary)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 20_000_000:
                    raise ValueError()
                image.verify()
                mimetype = Image.MIME[image.format]
        except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
            raise ValidationError(_('Choose a valid JPEG, PNG, or WebP image.')) from None
        attachment = self.env['ir.attachment'].sudo().create({
            'name': str(filename)[:128], 'datas': data, 'mimetype': mimetype,
            'res_model': self._name, 'res_id': self.id, 'company_id': self.company_id.id,
            'public': False,
        })
        return f'/web/image/{attachment.id}'

    def _publish_media(self, revision):
        urls = [revision.payload.get('image_url', '')]
        for blocks in revision.payload['blocks'].values():
            urls.extend(block.get('url', '') for block in blocks if block['type'] == 'image')
        ids = [int(match.group(1)) for url in urls if (match := re.fullmatch(r'/web/image/(\d+)', url))]
        if not ids:
            return
        documents = self.with_context(active_test=False).search(fields.Domain([('website_id', '=', self.website_id.id), ('company_id', '=', self.company_id.id)]))
        attachments = self.env['ir.attachment'].sudo().search(fields.Domain([
            ('id', 'in', ids), ('res_model', '=', self._name), ('res_id', 'in', documents.ids),
            ('company_id', '=', self.company_id.id),
        ]))
        attachments.write({'public': True})

    def _check_publishable(self, snapshot):
        def luminance(color):
            channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
            return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))
        for platform in ('web', 'flutter'):
            tokens = {**snapshot['design_tokens'], **snapshot['platform_overrides'][platform]}
            light, dark = sorted([luminance(tokens.get('color', '#172554')), luminance(tokens.get('background', '#ffffff'))], reverse=True)
            if (light + .05) / (dark + .05) < 4.5:
                raise ValidationError(_('Text contrast must be at least 4.5:1 before review.'))
            for blocks in snapshot['blocks'].values():
                for block in blocks:
                    if block['type'] == 'image' and (not block.get('url') or not block.get('alt', '').strip()):
                        raise ValidationError(_('Add an image and a description to every image block before review.'))
                    if block['type'] in ('hero', 'heading', 'text'):
                        style = {**tokens, **block.get('style', {})}
                        light, dark = sorted([luminance(style.get('color', '#172554')), luminance(style.get('background', '#ffffff'))], reverse=True)
                        if (light + .05) / (dark + .05) < 4.5:
                            raise ValidationError(_('Text contrast must be at least 4.5:1 before review.'))

    def _resolved_blocks(self, blocks):
        result = []
        references = [block['template_id'] for block in blocks if block['type'] == 'template']
        templates = self.env['ab_ecommerce_editor_template'].search(fields.Domain([
            ('id', 'in', references), ('website_id', '=', self.website_id.id), ('active', '=', True),
            ('scope', 'in', ['global', self.kind]),
        ]))
        by_id = {template.id: template for template in templates}
        for block in blocks:
            if block['type'] == 'template':
                template = by_id.get(block['template_id'])
                if not template:
                    raise ValidationError(_('A reusable block is missing from this website.'))
                for item in template.blocks or []:
                    copy = deepcopy(item)
                    copy['id'] = hashlib.sha256(f"{block['id']}:{copy['id']}".encode()).hexdigest()[:32]
                    copy['style'] = {**(template.design_tokens or {}), **copy.get('style', {})}
                    result.append(copy)
            else:
                result.append(deepcopy(block))
        validate_blocks(result)
        return result

    def _snapshot(self):
        self.ensure_one()
        self._check_content()
        return {
            'schema_version': 1,
            'kind': self.kind,
            'slug': self.slug,
            'website_id': self.website_id.id,
            'category': self.category or '',
            'image_url': self.image_url or '',
            'title': {'en_US': self.title_en, 'ar_001': self.title_ar or self.title_en},
            'summary': {'en_US': self.summary_en or '', 'ar_001': self.summary_ar or self.summary_en or ''},
            'blocks': {
                'en_US': self._resolved_blocks(self.blocks_en or []),
                'ar_001': self._resolved_blocks(self.blocks_ar or self.blocks_en or []),
            },
            'design_tokens': deepcopy(self.design_tokens or {}),
            'platform_overrides': {
                'web': deepcopy(self.web_overrides or {}),
                'flutter': deepcopy(self.flutter_overrides or {}),
            },
            'seo': {
                'title': {'en_US': self.seo_title_en or self.title_en, 'ar_001': self.seo_title_ar or self.title_ar or self.title_en},
                'description': {'en_US': self.seo_description_en or '', 'ar_001': self.seo_description_ar or self.seo_description_en or ''},
            },
        }

    def _save_revision(self):
        self.ensure_one()
        revision = self.env['ab_ecommerce_editor_revision'].sudo().create({
            'document_id': self.id,
            'number': self.version + 1,
            'payload': self._snapshot(),
            'author_id': self.env.uid,
        })
        super(EditorDocument, self).write({'version': revision.number})
        return revision

    def action_save_version(self):
        for document in self:
            document._require_role('editor')
            document._save_revision()
        return True

    def action_submit_review(self):
        for document in self:
            document._require_role('editor')
            if document.state not in ('draft', 'published'):
                raise ValidationError(_('Only a draft can be submitted for review.'))
            revision = document._save_revision()
            document._check_publishable(revision.payload)
            super(EditorDocument, document).write({'state': 'review', 'review_revision_id': revision.id})
        return True

    def action_return_draft(self):
        for document in self:
            document._require_role('reviewer')
            if document.state not in ('review', 'scheduled'):
                raise ValidationError(_('This content is not awaiting review or publication.'))
            super(EditorDocument, document).write({'state': 'draft', 'scheduled_at': False, 'review_revision_id': False, 'scheduled_by_id': False})
        return True

    def action_schedule(self, scheduled_at):
        for document in self:
            document._require_role('publisher')
            if document.state != 'review' or not scheduled_at or fields.Datetime.to_datetime(scheduled_at) <= fields.Datetime.now():
                raise ValidationError(_('Choose a future time for reviewed content.'))
            super(EditorDocument, document).write({'state': 'scheduled', 'scheduled_at': scheduled_at, 'scheduled_by_id': self.env.uid})
        return True

    def action_publish(self):
        for document in self:
            document._require_role('publisher')
            if document.state != 'review' or not document.review_revision_id:
                raise ValidationError(_('Submit this content for review before publishing.'))
            revision = document.review_revision_id
            document._publish_media(revision)
            revision._release(self.env.user)
            super(EditorDocument, document).write({
                'state': 'published', 'published_revision_id': revision.id,
                'published_at': fields.Datetime.now(), 'scheduled_at': False,
            })
        return True

    @api.model
    def _publish_due(self):
        due = self.sudo().search(fields.Domain([('state', '=', 'scheduled'), ('scheduled_at', '<=', fields.Datetime.now())]), limit=100).try_lock_for_update(allow_referencing=True)
        for document in due:
            revision = document.review_revision_id
            publisher = document.scheduled_by_id
            if not revision or not publisher.active or not publisher.has_group('ab_ecommerce_editor.group_editor_publisher') or document.company_id not in publisher.company_ids:
                continue
            document._publish_media(revision)
            revision._release(publisher)
            super(EditorDocument, document).write({
                'state': 'published', 'published_revision_id': revision.id,
                'published_at': fields.Datetime.now(), 'scheduled_at': False,
            })

    def action_restore_revision(self, revision_id):
        self.ensure_one()
        self._require_role('editor')
        if self.state in ('review', 'scheduled'):
            raise ValidationError(_('Return this content to draft before editing.'))
        revision = self.env['ab_ecommerce_editor_revision'].search(fields.Domain([
            ('id', '=', revision_id), ('document_id', '=', self.id),
        ]), limit=1)
        if not revision:
            raise ValidationError(_('This version does not belong to the document.'))
        payload = revision.payload
        super().write({
            'title_en': payload['title']['en_US'], 'title_ar': payload['title']['ar_001'],
            'summary_en': payload['summary']['en_US'], 'summary_ar': payload['summary']['ar_001'],
            'blocks_en': payload['blocks']['en_US'], 'blocks_ar': payload['blocks']['ar_001'],
            'design_tokens': payload['design_tokens'],
            'web_overrides': payload['platform_overrides']['web'],
            'flutter_overrides': payload['platform_overrides']['flutter'],
            'seo_title_en': payload['seo']['title']['en_US'],
            'seo_title_ar': payload['seo']['title']['ar_001'],
            'seo_description_en': payload['seo']['description']['en_US'],
            'seo_description_ar': payload['seo']['description']['ar_001'],
            'category': payload['category'], 'image_url': payload['image_url'],
            'state': 'draft', 'scheduled_at': False,
            'draft_token': str(uuid.uuid4()),
        })
        return True


class EditorRevision(models.Model):
    _name = 'ab_ecommerce_editor_revision'
    _description = 'eCommerce Editor Version'
    _order = 'number desc, id desc'

    document_id = fields.Many2one('ab_ecommerce_editor_document', required=True, ondelete='restrict')
    website_id = fields.Many2one(related='document_id.website_id', store=True)
    company_id = fields.Many2one(related='document_id.company_id', store=True)
    number = fields.Integer(required=True)
    payload = fields.Json(required=True)
    author_id = fields.Many2one('res.users', required=True)
    released_at = fields.Datetime(readonly=True)
    released_by_id = fields.Many2one('res.users', readonly=True)

    _unique_number = models.Constraint(
        'UNIQUE(document_id, number)',
        'The version number must be unique for this document.',
    )

    def write(self, values):
        raise AccessError(_('Saved versions cannot be changed.'))

    def _release(self, publisher):
        self.ensure_one()
        if not self.released_at:
            super(EditorRevision, self.sudo()).write({
                'released_at': fields.Datetime.now(), 'released_by_id': publisher.id,
            })

    def unlink(self):
        raise AccessError(_('Saved versions cannot be deleted.'))
