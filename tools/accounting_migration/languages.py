"""Discover delegated source preferences and install target languages before COPY."""
from psycopg2 import sql
from common import MigrationError, save_json
from progress import current

REQUIRED_LANGUAGES = ('en_US', 'ar_001')


def discover_languages(connection, inventory):
    partner = inventory.get('models', {}).get('res.partner', {})
    if partner.get('table_kind') not in ('r', 'p') or 'lang' not in partner.get('columns', {}):
        raise MigrationError('Source schema has no stored res.partner.lang; language discovery requires an explicit adapter')
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SELECT DISTINCT lang FROM {} WHERE lang IS NOT NULL AND lang <> ''").format(
            sql.Identifier('public', partner['table'])))
        languages = {row[0] for row in cursor if row[0] and row[0].strip()}
    return list(REQUIRED_LANGUAGES) + sorted(languages - set(REQUIRED_LANGUAGES))


def install_languages(env, stage, requested):
    """Called after module installation, before the initialization transaction commits."""
    if not isinstance(requested, list) or not all(isinstance(code, str) and code for code in requested):
        raise MigrationError('Required language list is missing or invalid; start a fresh migration')
    languages = list(dict.fromkeys([*REQUIRED_LANGUAGES, *requested]))
    report = dict(required=languages, activated=[], translations_loaded=False, complete=False, phase='activation')
    save_json(stage / 'languages.json', report)
    try:
        current().begin('languages', operation='activate requested languages', total=len(languages))
        for code in languages:
            current().operation('activate ' + code)
            print(f'Activate language: {code}', flush=True)
            language = env['res.lang']._activate_lang(code)
            if not language or not language.active:
                raise MigrationError(f'Unsupported or inactive source language: {code}')
            report['activated'].append(code)
            current().advance(1)
        report['phase'] = 'module translations'
        save_json(stage / 'languages.json', report)
        current().begin('translations', operation='load installed module translations')
        print('Load installed module translations: ' + ', '.join(languages), flush=True)
        env['ir.module.module'].search([('state', '=', 'installed')])._update_translations(filter_lang=languages)
        env.flush_all()
        active = set(env['res.lang'].with_context(active_test=False).search([
            ('code', 'in', languages), ('active', '=', True)]).mapped('code'))
        if set(languages) != active:
            raise MigrationError('Language activation verification failed: ' + ', '.join(sorted(set(languages) - active)))
        report.update(translations_loaded=True, complete=True, phase='complete')
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        raise MigrationError(f'Language setup failed during {report["phase"]}; see languages.json' +
                             (f': {exc}' if isinstance(exc, MigrationError) else '')) from None
    finally:
        save_json(stage / 'languages.json', report)
    return report
