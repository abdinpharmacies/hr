import json

from odoo import _
from odoo.exceptions import ValidationError
from odoo.tools import file_open


def homepage_sections():
    with file_open('ab_ecommerce_editor/static/schema/homepage-sections.json') as source:
        return json.load(source)


def default_home_blocks():
    return [{'id': section['type'], 'type': section['type'], 'active': True} for section in homepage_sections()]


def validate_home_content(block):
    section = next((s for s in homepage_sections() if s['type'] == block['type']), None)
    content = block.get('content', {})
    if not section or not isinstance(content, dict):
        raise ValidationError(_('This homepage section is invalid.'))
    allowed = {field['key'] for field in section['fields']}
    if set(content) - allowed or any(not isinstance(value, str) or len(value) > 4000 for value in content.values()):
        raise ValidationError(_('This homepage section is invalid.'))
