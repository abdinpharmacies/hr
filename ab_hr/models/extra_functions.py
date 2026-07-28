from collections.abc import Iterable


def get_modified_name(name):
    if isinstance(name, str):
        replacement = 'أإآ'
        for s in replacement:
            name = name.replace(s, 'ا')

        name = name.replace('ؤ', 'و')
        name = name.replace('ى', 'ي')
        name = name.replace('  ', '%')
        return name

    if isinstance(name, Iterable) and not isinstance(name, (bytes, dict)):
        return type(name)(
            get_modified_name(item) if isinstance(item, str) else item
            for item in name
        )

    return name
