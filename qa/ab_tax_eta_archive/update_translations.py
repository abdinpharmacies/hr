"""Append missing entries from the Odoo-exported POT; retain existing translations."""
import re
import polib
from pathlib import Path
from babel.messages.pofile import read_po

root = Path(__file__).resolve().parents[2] / 'ab_tax_eta_archive/i18n'
pot = polib.pofile(str(Path(__file__).with_name('ab_tax_eta_archive.pot')))
translations = {
    'Checkpoint': 'نقطة الاستئناف', 'Completed At': 'اكتمل في',
    'Created by': 'أنشئ بواسطة', 'Created on': 'تاريخ الإنشاء',
    'Detail Json': 'تفاصيل JSON', 'Details incomplete': 'التفاصيل غير مكتملة',
    'Display Name': 'الاسم المعروض', 'ETA Archive Configuration': 'إعداد أرشيف الضرائب',
    'ETA Daily Retrieval': 'الاسترجاع اليومي للضرائب', 'ETA Invoice': 'فاتورة الضرائب',
    'ETA Receipt': 'إيصال الضرائب', 'Export Format Version': 'إصدار تنسيق التصدير',
    'File generated': 'تم إنشاء الملف', 'File generation failed': 'فشل إنشاء الملف',
    'Generation Error': 'خطأ إنشاء الملف', 'Generation State': 'حالة إنشاء الملف',
    'ID': 'المعرّف', 'Importing': 'جارٍ الاستيراد', 'Internal': 'داخلي',
    'Invoice Client': 'عميل الفواتير', 'Issuer': 'المصدر', 'Last Error': 'آخر خطأ',
    'Last Updated by': 'آخر تحديث بواسطة', 'Last Updated on': 'تاريخ آخر تحديث',
    'Next Attempt At': 'موعد المحاولة التالية', 'No records': 'لا توجد سجلات',
    'Only one ETA retrieval is allowed for each day and stream.':
        'يسمح بعملية استرجاع ضريبية واحدة فقط لكل يوم ونوع واتجاه.',
    'Package': 'الحزمة', 'Partial': 'مكتمل جزئيًا', 'Raw Json': 'بيانات JSON الأصلية',
    'Receipt Client': 'عميل الإيصالات', 'Receipt Issue Dates Json': 'تواريخ إصدار الإيصالات بصيغة JSON',
    'Receiver': 'المستلم', 'Retrieval incomplete': 'الاسترجاع غير مكتمل',
    'Safety Delay Hours': 'مهلة الأمان بالساعات',
    'Safety delay must be between 0 and 8760 hours.': 'يجب أن تكون مهلة الأمان بين صفر و8760 ساعة.',
    'Send to Telegram': 'إرسال إلى تيليجرام', 'Sync': 'الاسترجاع',
    'Telegram Chat': 'محادثة تيليجرام', 'Telegram Message': 'رسالة تيليجرام',
    'Available': 'متاح', 'Preparing': 'جارٍ التجهيز', 'Preparation failed': 'فشل التجهيز',
    'Expired or deleted': 'منتهي الصلاحية أو محذوف', 'Package not found': 'الحزمة غير موجودة',
    'Remote Error': 'خطأ مصلحة الضرائب', 'Remote Status': 'حالة الحزمة لدى مصلحة الضرائب',
    'Status Checked At': 'وقت فحص الحالة', 'Status Page': 'صفحة فحص الحالة',
    'Generate Files': 'إنشاء الملفات', 'Generation Requested': 'إنشاء الملفات مطلوب',
    'Generation Retry At': 'موعد إعادة محاولة إنشاء الملفات',
    'ETA failed to prepare package %(package)s.': 'فشلت مصلحة الضرائب في تجهيز الحزمة %(package)s.',
    'ETA package %(package)s has expired or was deleted.':
        'انتهت صلاحية الحزمة %(package)s لدى مصلحة الضرائب أو تم حذفها.',
    'ETA package %(package)s was not found; verify its ID and credentials.':
        'لم يتم العثور على الحزمة %(package)s؛ تحقق من معرفها وبيانات الاتصال.',
    'ETA package status response is invalid.': 'استجابة حالة الحزمة من مصلحة الضرائب غير صالحة.',
    'Request History': 'سجل طلبات الحزمة',
    'File Content Digest': 'بصمة محتوى الملف', 'File Rows': 'صفوف الملف',
    'ETA package renewal limit reached; verify the request in the ETA portal.':
        'تم بلوغ الحد الأقصى لتجديد الحزمة؛ تحقق من الطلب في بوابة مصلحة الضرائب.',
}
for language in ('ar', 'ar_001'):
    path = root / (language + '.po')
    text = path.read_text(encoding='utf-8')
    existing = polib.pofile(str(path))
    count = 0
    for message in pot:
        if not message.msgid:
            continue
        entry = existing.find(message.msgid)
        if not entry:
            if message.msgid not in translations:
                raise RuntimeError('Missing Arabic translation: ' + message.msgid)
            entry = polib.POEntry(msgid=message.msgid, msgstr=translations[message.msgid],
                                 occurrences=message.occurrences, comment=message.comment,
                                 flags=message.flags)
            text = text.rstrip() + '\n\n' + str(entry)
            count += 1
        elif message.msgid in translations or message.msgid in ('ETA Retrievals', 'Ready'):
            # Babel discards Odoo's model references because they contain colons.
            # Merge references using polib while leaving existing prose untouched.
            missing = [occ for occ in message.occurrences if occ not in entry.occurrences]
            if missing:
                marker = 'msgid "' + message.msgid + '"'
                refs = ['#: ' + occurrence + (':' + number if number else '')
                        for occurrence, number in missing]
                at = text.index(marker)
                text = text[:at] + '\n'.join(refs) + '\n' + text[at:]
    path.write_text(text.rstrip()+'\n', encoding='utf-8')
    catalog = read_po(open(path, 'rb'), locale=language)
    errors = [(message.id, list(message.check(catalog))) for message in catalog]
    errors = [(key, error) for key, error in errors if error]
    if errors:
        raise RuntimeError(errors)
    print(language, 'appended', count, 'entries; references merged; Babel format checks passed')
