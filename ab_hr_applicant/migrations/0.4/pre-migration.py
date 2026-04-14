def migrate(cr, version):
    cr.execute(
        """
        UPDATE res_country_state s
        SET name = v.ar_name
        FROM (
            VALUES
                ('ALX', 'الإسكندرية'),
                ('ASN', 'أسوان'),
                ('AST', 'أسيوط'),
                ('BA', 'البحر الأحمر'),
                ('BH', 'البحيرة'),
                ('BNS', 'بني سويف'),
                ('C', 'القاهرة'),
                ('DK', 'الدقهلية'),
                ('DT', 'دمياط'),
                ('FYM', 'الفيوم'),
                ('GH', 'الغربية'),
                ('GZ', 'الجيزة'),
                ('HU', 'حلوان'),
                ('IS', 'الإسماعيلية'),
                ('JS', 'جنوب سيناء'),
                ('KB', 'القليوبية'),
                ('KFS', 'كفر الشيخ'),
                ('KN', 'قنا'),
                ('LX', 'الأقصر'),
                ('MN', 'المنيا'),
                ('MNF', 'المنوفية'),
                ('MT', 'مطروح'),
                ('PTS', 'بورسعيد'),
                ('SHG', 'سوهاج'),
                ('SHR', 'الشرقية'),
                ('SIN', 'شمال سيناء'),
                ('SU', 'السادس من أكتوبر'),
                ('SUZ', 'السويس'),
                ('WAD', 'الوادي الجديد')
        ) AS v(code, ar_name)
        WHERE s.code = v.code
          AND s.country_id = (SELECT id FROM res_country WHERE code = 'EG' LIMIT 1)
        """
    )
