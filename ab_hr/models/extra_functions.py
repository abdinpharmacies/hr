from odoo import fields


def with_normalized_name(domain, operator, value):
    """Also match the normalized Arabic spelling used by existing HR lookups."""
    if not isinstance(value, str) or not operator.endswith('like'):
        return domain
    spelling = value.translate(str.maketrans("أإآؤى", "اااوي")).replace("  ", "%")
    if spelling == value:
        return domain
    alternative = fields.Domain('name', operator, spelling)
    if operator in fields.Domain.NEGATIVE_OPERATORS:
        return domain & alternative
    return domain | alternative
