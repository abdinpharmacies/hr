def get_modified_name(name):
    replacement = 'أإآ'
    for s in replacement:
        name = name.replace(s, 'ا')

    name = name.replace('ؤ', 'و')
    name = name.replace('ى', 'ي')
    name = name.replace('  ', '%')
    return name
