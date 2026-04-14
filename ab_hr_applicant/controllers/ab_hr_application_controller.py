# -*- coding: utf-8 -*-
import io
import random
import string
import time
from datetime import datetime, date

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from odoo import http
from odoo.http import request
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


CAPTCHA_SESSION_KEY = 'ab_hr_applicant_captcha'
CAPTCHA_TTL_SECONDS = 180

ALLOWED_FIELDS = {
    'name', 'national_identity', 'military_status', 'birth_date',
    'governorate_id', 'city_id', 'address', 'religion',
    'mobile', 'telephone', 'email', 'gender', 'qualification',
    'nationality', 'graduate_date', 'marital_status',
    'type_of_form', 'required_job_id', 'expected_salary',
    'bconnect_experience', 'morning', 'evening', 'after_midnight',
}


class AbHrWebsiteApplication(http.Controller):
    def _generate_captcha_code(self, length=5):
        return ''.join(random.choice(string.digits) for _i in range(length))

    def _get_captcha_font(self, size=36):
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _build_captcha_image(self, code):
        width, height = 220, 74
        image = Image.new('RGB', (width, height), (246, 248, 251))
        draw = ImageDraw.Draw(image)
        resampling = Image.Resampling.BICUBIC if hasattr(Image, 'Resampling') else Image.BICUBIC

        for _i in range(280):
            draw.point(
                (random.randint(0, width - 1), random.randint(0, height - 1)),
                fill=(
                    random.randint(120, 205),
                    random.randint(120, 205),
                    random.randint(120, 205),
                ),
            )

        for _i in range(8):
            draw.line(
                (
                    random.randint(0, width - 1),
                    random.randint(0, height - 1),
                    random.randint(0, width - 1),
                    random.randint(0, height - 1),
                ),
                fill=(
                    random.randint(165, 230),
                    random.randint(165, 230),
                    random.randint(165, 230),
                ),
                width=1,
            )

        x = 14
        for char in code:
            char_font = self._get_captcha_font(random.randint(34, 42))
            char_canvas = Image.new('RGBA', (60, 60), (255, 255, 255, 0))
            char_draw = ImageDraw.Draw(char_canvas)
            char_draw.text(
                (10, 4),
                char,
                font=char_font,
                fill=(
                    random.randint(18, 70),
                    random.randint(18, 70),
                    random.randint(18, 70),
                ),
            )
            rotated = char_canvas.rotate(
                random.randint(-35, 35),
                resample=resampling,
                expand=True,
            )
            image.paste(rotated, (x, random.randint(6, 16)), rotated)
            x += random.randint(36, 40)

        for _i in range(3):
            points = []
            base_y = random.randint(18, height - 16)
            for x_pos in range(0, width + 1, 16):
                points.append((x_pos, base_y + random.randint(-12, 12)))
            draw.line(
                points,
                fill=(
                    random.randint(28, 95),
                    random.randint(28, 95),
                    random.randint(28, 95),
                ),
                width=random.randint(2, 3),
            )

        for _i in range(6):
            x0 = random.randint(0, width - 46)
            y0 = random.randint(0, height - 30)
            x1 = x0 + random.randint(30, 68)
            y1 = y0 + random.randint(16, 34)
            draw.arc(
                (x0, y0, x1, y1),
                start=random.randint(0, 180),
                end=random.randint(181, 360),
                fill=(
                    random.randint(95, 160),
                    random.randint(95, 160),
                    random.randint(95, 160),
                ),
                width=1,
            )

        image = image.filter(ImageFilter.GaussianBlur(0.6))
        image = image.filter(ImageFilter.SHARPEN)
        stream = io.BytesIO()
        image.save(stream, format='PNG')
        return stream.getvalue()

    @http.route('/jobs/apply', type='http', auth='public', website=True, csrf=True)
    def apply_form(self, **kw):
        env = request.env
        jobs = env['ab_required_job'].sudo().search([('is_publish', '=', True)])
        egypt = env['res.country'].sudo().search([('code', '=', 'EG')], limit=1)
        govs = env['res.country.state'].sudo().search([('country_id', '=', egypt.id)])
        max_birth_date = (date.today() - relativedelta(years=18)).isoformat()
        selected_job_id = False
        selected_param = kw.get('required_job_id') or kw.get('job_id')
        if selected_param:
            try:
                selected_job_id = int(selected_param)
            except Exception:
                selected_job_id = False
        if selected_job_id:
            selected_job = env['ab_required_job'].sudo().browse(selected_job_id)
            if not selected_job.exists():
                selected_job_id = False

        return request.render('ab_hr_applicant.website_apply_form', {
            'jobs': jobs,
            'govs': govs,
            'egypt': egypt,
            'error': kw.get('error'),
            'post': kw,
            'max_birth_date': max_birth_date,
            'selected_job_id': selected_job_id,
        })

    @http.route('/jobs/captcha/image', type='http', auth='public', website=True, methods=['GET'], csrf=False, sitemap=False)
    def captcha_image(self, **kw):
        code = self._generate_captcha_code()
        request.session[CAPTCHA_SESSION_KEY] = {
            'code': code,
            'created_at': int(time.time()),
        }
        image_bytes = self._build_captcha_image(code)
        return request.make_response(
            image_bytes,
            headers=[
                ('Content-Type', 'image/png'),
                ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
                ('Pragma', 'no-cache'),
            ],
        )

    @http.route('/jobs/cities_http', type='http', auth='public', website=True, methods=['GET'])
    def get_cities_http(self, governorate_id=None, **kw):
        try:
            gid = int(governorate_id or 0)
        except Exception:
            gid = 0

        cities = request.env['ab_city'].sudo().search([('state_id', '=', gid)])
        data = [{'id': c.id, 'name': c.display_name} for c in cities]
        return request.make_json_response(data)

    @http.route('/jobs/apply/submit', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def apply_submit(self, **post):
        env = request.env
        captcha_payload = request.session.get(CAPTCHA_SESSION_KEY)
        entered_captcha = (post.get('captcha_input') or '').strip()
        request.session.pop(CAPTCHA_SESSION_KEY, None)

        expected_captcha = captcha_payload
        created_at = 0
        if isinstance(captcha_payload, dict):
            expected_captcha = captcha_payload.get('code')
            created_at = captcha_payload.get('created_at') or 0

        is_expired = bool(created_at and (time.time() - float(created_at) > CAPTCHA_TTL_SECONDS))

        if not expected_captcha or entered_captcha != expected_captcha or is_expired:
            return request.redirect('/jobs/apply?error=Invalid%20verification%20code.%20Please%20try%20again.')

        vals = {}
        for k in ALLOWED_FIELDS:
            if k in post:
                vals[k] = post.get(k)
        if not vals.get('required_job_id') and post.get('job_id'):
            vals['required_job_id'] = post.get('job_id')

        int_fields = ['governorate_id', 'city_id', 'nationality', 'required_job_id', 'expected_salary']
        for f in int_fields:
            if vals.get(f):
                try:
                    vals[f] = int(vals[f])
                except Exception:
                    vals[f] = False

        if vals.get('required_job_id'):
            selected_job = env['ab_required_job'].sudo().browse(vals['required_job_id'])
            if not selected_job.exists():
                vals['required_job_id'] = False

        bool_fields = ['bconnect_experience', 'morning', 'evening', 'after_midnight']
        for f in bool_fields:
            vals[f] = True if post.get(f) in ('on', 'true', 'True', '1') else False

        if not vals.get('nationality'):
            egypt = env['res.country'].sudo().search([('code', '=', 'EG')], limit=1)
            vals['nationality'] = egypt.id if egypt else False

        required_fields = [
            'name', 'national_identity', 'birth_date', 'gender',
            'governorate_id', 'city_id', 'address', 'religion',
            'mobile', 'qualification', 'graduate_date', 'marital_status',
            'type_of_form', 'required_job_id', 'expected_salary', 'nationality'
        ]
        for rf in required_fields:
            if not vals.get(rf):
                return request.redirect('/jobs/apply?error=Missing%20required%20field:%20' + rf)

        if vals.get('gender') == 'male' and not vals.get('military_status'):
            return request.redirect('/jobs/apply?error=Missing%20required%20field:%20military_status')

        if vals.get('gender') == 'female' and not vals.get('military_status'):
            vals['military_status'] = 'unrequired'

        exp_commands = []
        exp_company = request.httprequest.form.getlist('exp_company[]')
        exp_title = request.httprequest.form.getlist('exp_title[]')
        exp_from = request.httprequest.form.getlist('exp_from[]')
        exp_to = request.httprequest.form.getlist('exp_to[]')
        exp_reason = request.httprequest.form.getlist('exp_reason[]')
        exp_salary = request.httprequest.form.getlist('exp_salary[]')

        for i in range(len(exp_company)):
            if (exp_company[i] or '').strip():
                exp_commands.append((0, 0, {
                    'company_name': exp_company[i],
                    'job_title': exp_title[i] if i < len(exp_title) else False,
                    'starting_date': exp_from[i] if i < len(exp_from) else False,
                    'ending_date': exp_to[i] if i < len(exp_to) else False,
                    'reason_for_leaving': exp_reason[i] if i < len(exp_reason) else False,
                    'salary': exp_salary[i] if i < len(exp_salary) else False,
                }))

        course_commands = []
        c_spec = request.httprequest.form.getlist('course_specialty[]')
        c_org = request.httprequest.form.getlist('course_org[]')
        c_period = request.httprequest.form.getlist('course_period[]')
        c_grade = request.httprequest.form.getlist('course_grade[]')

        for i in range(len(c_spec)):
            if (c_spec[i] or '').strip():
                course_commands.append((0, 0, {
                    'specialty': c_spec[i],
                    'organization': c_org[i] if i < len(c_org) else False,
                    'time_period': c_period[i] if i < len(c_period) else False,
                    'grade': c_grade[i] if i < len(c_grade) else False,
                }))

        vals['experience_ids'] = exp_commands
        vals['trainingcourses_ids'] = course_commands

        Application = env['ab_hr_application'].sudo()
        jobs = env['ab_required_job'].sudo().search([('is_publish', '=', True)])

        egypt = env['res.country'].sudo().search([('code', '=', 'EG')], limit=1)
        govs = env['res.country.state'].sudo().search([('country_id', '=', egypt.id)])

        cities = env['ab_city'].sudo().browse()
        if vals.get('governorate_id'):
            cities = env['ab_city'].sudo().search([
                ('state_id', '=', vals.get('governorate_id'))
            ])
        try:

            existing = Application.search([
                ('national_identity', '=', vals.get('national_identity')),
                ('required_job_id', '=', vals.get('required_job_id')),
            ], limit=1)

            if existing:
                existing.write(vals)

                existing.experience_ids.unlink()
                if vals.get('experience_ids'):
                    existing.write({'experience_ids': vals['experience_ids']})
                existing.trainingcourses_ids.unlink()
                if vals.get('trainingcourses_ids'):
                    existing.write({'trainingcourses_ids': vals['trainingcourses_ids']})
            else:
                Application.create(vals)
        except ValidationError as e:
            return request.render(
                'ab_hr_applicant.website_apply_form',
                {
                    'error': str(e),
                    'post': post,
                    'jobs': jobs,
                    'govs': govs,
                    'cities': cities,
                    'egypt': egypt,
                }
            )

        return request.redirect('/jobs/apply/thanks')

    @http.route('/jobs/apply/thanks', type='http', auth='public', website=True)
    def apply_thanks(self, **kw):
        return request.render('ab_hr_applicant.website_apply_thanks', {})
