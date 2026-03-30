def migrate(cr, version):
    cr.execute(
        """
        UPDATE res_country_state s
        SET name = v.en_name
        FROM (
            VALUES
                ('ALX', 'Alexandria'),
                ('ASN', 'Aswan'),
                ('AST', 'Asyut'),
                ('BA', 'Red Sea'),
                ('BH', 'Beheira'),
                ('BNS', 'Beni Suef'),
                ('C', 'Cairo'),
                ('DK', 'Dakahlia'),
                ('DT', 'Damietta'),
                ('FYM', 'Faiyum'),
                ('GH', 'Gharbia'),
                ('GZ', 'Giza'),
                ('HU', 'Helwan'),
                ('IS', 'Ismailia'),
                ('JS', 'South Sinai'),
                ('KB', 'Qalyubia'),
                ('KFS', 'Kafr el-Sheikh'),
                ('KN', 'Qena'),
                ('LX', 'Luxor'),
                ('MN', 'Minya'),
                ('MNF', 'Monufia'),
                ('MT', 'Matrouh'),
                ('PTS', 'Port Said'),
                ('SHG', 'Sohag'),
                ('SHR', 'Al Sharqia'),
                ('SIN', 'North Sinai'),
                ('SU', '6th of October'),
                ('SUZ', 'Suez'),
                ('WAD', 'New Valley')
        ) AS v(code, en_name)
        WHERE s.code = v.code
          AND s.country_id = (SELECT id FROM res_country WHERE code = 'EG' LIMIT 1)
        """
    )
