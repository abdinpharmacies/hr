import re

from lxml import etree, html
from markupsafe import escape

from odoo import _
from odoo.exceptions import ValidationError


SNIPPETS = frozenset('s_title s_text_block s_text_image s_image_text s_three_columns s_features s_picture s_cta_box s_card s_button s_hr s_badge s_allow_columns s_banner s_media_list s_features_grid s_numbers s_comparisons s_call_to_action s_company_team s_cards_grid'.split())
TAGS = frozenset('section article div span p h1 h2 h3 h4 h5 h6 a img figure figcaption ul ol li br hr b strong i em u s small sub sup blockquote pre code table thead tbody tfoot tr td th font mark'.split())
CLASSES = re.compile(
    r'(?:container(?:-fluid)?|row|col(?:-(?:sm|md|lg|xl|xxl))?(?:-\d{1,2})?|offset-(?:lg-)?\d{1,2}|'
    r'(?:p[trblxyse]?|m[trblxyse]?|g[xy]?|gap)-(?:sm-|md-|lg-|xl-|xxl-)?(?:auto|[0-5])|p[trbl]\d{1,3}|'
    r'g-(?:col-(?:lg-)?|height-)\d{1,2}|float-(?:start|end)|overflow-hidden|'
    r'figure(?:-img|-caption)?|list-group(?:-flush|-item)?|small|img|'
    r's_(?:features(?:_grid)?_(?:content|icon)|media_list_(?:body|img|img_wrapper|item)|number|nb_column_fixed|'
    r'col_no_(?:bgcolor|resize)|blockquote(?:_(?:author|avatar|icon|infos|line_elt|quote|with_line|wrap_icon))?)|'
    r'(?:text|bg|border|rounded|btn|badge|table|card|ratio|align|justify|flex|display|fw|fst|fs|lh|w|h|img|shadow|fa|d)-[a-z0-9-]+|'
    r'h[1-6](?:-fs)?|lead|btn|card|table|ratio|badge|border|rounded|shadow|fa|'
    r'o_(?:cc[1-6]?|container_small|card_img\w*|text_columns|grid_mode|grid_item(?:_image)?|colored_level|'
    r'default_snippet_text|small|editable_media|snippet_mobile_invisible|snippet_desktop_invisible))'
)
STYLE_PROPERTY = re.compile(r'(?:color|background-color|font-(?:size|weight|style|family)|text-(?:align|decoration)|vertical-align|(?:min-|max-)?(?:width|height)|(?:border|padding|margin)(?:-(?:left|right|top|bottom|width|color|style|radius)){0,2}|grid-(?:area|row|column)|gap|--(?:card-img-size-h|card-spacer-[xy]|grid-item-padding-[xy]|grid-row-height))')
STYLE_VALUE = re.compile(r'(?:[\w#.,% /-]+|(?:rgba?|hsla?)\([\d.,% /-]+\)|var\(--(?:o-color-[1-5]|bs-[a-z-]+)\))(?:\s*!important)?', re.ASCII)


def clean_section(source):
    if not isinstance(source, str) or len(source) > 120_000:
        raise ValidationError(_('The website section is too large.'))
    try:
        root = html.fragment_fromstring(source, create_parent='div')
    except (ValueError, etree.ParserError):
        raise ValidationError(_('Invalid website section.')) from None
    for element in list(root.iterdescendants()):
        if element.tag not in TAGS:
            element.drop_tree()
            continue
        for key, value in list(element.attrib.items()):
            del element.attrib[key]
            if key == 'class':
                value = ' '.join(token for token in value.split() if token in SNIPPETS or CLASSES.fullmatch(token))
            elif key == 'style':
                declarations = []
                for declaration in value.split(';'):
                    name, sep, val = declaration.partition(':')
                    name, val = name.strip().lower(), val.strip()
                    if sep and STYLE_PROPERTY.fullmatch(name) and STYLE_VALUE.fullmatch(val):
                        declarations.append(f'{name}: {val}')
                value = '; '.join(declarations)
            elif key == 'data-snippet' and value in SNIPPETS:
                pass
            elif key == 'color' and element.tag == 'font' and re.fullmatch(r'#[a-fA-F0-9]{3,8}', value):
                pass
            elif key == 'dir' and value in ('ltr', 'rtl', 'auto'):
                pass
            elif key in ('alt', 'title', 'data-name'):
                value = value[:512]
            elif key in ('colspan', 'rowspan') and value.isascii() and value.isdigit() and len(value) <= 2:
                pass
            elif (key == 'href' and element.tag == 'a') or (key == 'src' and element.tag == 'img'):
                from .editor_document import validate_url
                if key != 'href' or not re.fullmatch(r'#[\w-]*', value):
                    validate_url(value, image=key == 'src')
            else:
                continue
            if value:
                element.set(key, value)
    cleaned = str(escape(root.text or '')) + ''.join(html.tostring(child, encoding='unicode') for child in root)
    if len(cleaned) > 120_000:
        raise ValidationError(_('The website section is too large.'))
    return cleaned
