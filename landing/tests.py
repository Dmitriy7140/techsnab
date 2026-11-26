import json
import re
from datetime import UTC, date, datetime
from importlib import import_module
from unittest.mock import patch
from uuid import uuid4
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import FirstVisit, Lead, TrafficEvent
from .reviews.models import Review


STATIC = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


def grant(user, app, *permissions):
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label=app, codename__in=permissions))


@override_settings(STORAGES=STATIC, PUBLIC_REVIEWS=False)
class LandingTests(TestCase):
    def test_opt_in_withdrawal_and_legacy_cookies(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get('/')
        self.assertContains(page, 'Разрешить cookie')
        self.assertFalse('th37_visitor' in client.cookies)
        self.assertFalse('th37_consent' in client.cookies)
        click = {'id': uuid4(), 'kind': 'click', 'target': '#products'}
        client.post('/events/consent/', {'choice': 'allow'})
        self.assertFalse(FirstVisit.objects.exists())
        token = client.cookies['csrftoken'].value
        client.post('/events/', {**click, 'csrfmiddlewaretoken': token})
        self.assertFalse(TrafficEvent.objects.exists())
        for choice in ['deny', 'allow', 'allow']:
            client.post('/events/consent/', {'choice': choice, 'csrfmiddlewaretoken': token})
            self.assertEqual(FirstVisit.objects.count(), int(choice == 'allow'))
        self.assertEqual(TrafficEvent.objects.filter(kind='view').count(), 1)
        client.get('/')
        client.post('/events/', {**click, 'csrfmiddlewaretoken': token})
        self.assertEqual(TrafficEvent.objects.filter(kind='click').count(), 1)
        client.post('/events/consent/', {'choice': 'deny', 'csrfmiddlewaretoken': token})
        self.assertFalse(client.cookies['th37_visitor'].value)
        client.post('/events/', {**click, 'id': uuid4(), 'csrfmiddlewaretoken': token})
        self.assertEqual(TrafficEvent.objects.count(), 2)

        legacy = Client()
        old_id = str(uuid4())
        old_response = HttpResponse()
        old_response.set_signed_cookie('th37_visitor', old_id, salt='traffic')
        legacy.cookies.update(old_response.cookies)
        self.assertContains(legacy.get('/'), 'data-state=""')
        legacy.post('/events/', click)
        legacy.post('/events/consent/', {'choice': 'allow'})
        self.assertEqual(FirstVisit.objects.count(), 1)
        returning = RequestFactory().get('/')
        returning.COOKIES['th37_visitor'] = legacy.cookies['th37_visitor'].value
        self.assertEqual(returning.get_signed_cookie('th37_visitor', salt='traffic'), old_id)
        self.assertEqual(Client().post('/events/consent/', {'choice': 'allow'}, HTTP_DNT='1')['X-Analytics-Choice'], 'deny')

    def test_form_and_clicks_reach_the_same_visitor_history(self):
        page = self.client.get('/')
        ticket = page.context['form'].initial['submission_id']
        self.client.post('/', {'submission_id': ticket, 'name': 'Тест'})
        self.assertFalse(Lead.objects.exists())
        self.client.post('/events/consent/', {'choice': 'allow', 'referrer': 'https://ref.example/private?q=x'})
        details = {'submission_id': ticket, 'name': 'Тест', 'phone': '000', 'cargo': 'Сода'}
        for _ in range(2):
            self.assertRedirects(self.client.post('/', details), '/#contact', fetch_redirect_response=False)
        lead = Lead.objects.get()
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertIsNotNone(lead.visitor)
        click = {'id': uuid4(), 'kind': 'click', 'target': '#contact', 'label': 'Рассчитать стоимость'}
        for _ in range(2):
            self.assertEqual(self.client.post('/events/', click).status_code, 204)
        self.assertEqual(TrafficEvent.objects.get(kind='click').visitor, lead.visitor)
        self.assertEqual(self.client.post('/events/', {**click, 'target': 'https://unknown.example/'}).status_code, 400)
        self.assertEqual(self.client.post('/events/', {'id': uuid4(), 'kind': 'view', 'referrer': 'https://ref.example/private?q=x'}).status_code, 204)
        self.assertEqual(TrafficEvent.objects.get(kind='view').source, 'ref.example')
        self.assertEqual(Client(enforce_csrf_checks=True).post('/events/', click).status_code, 403)
        anon = Client()
        anon.post('/', {'name': 'Другой', 'phone': '123'})
        self.assertIsNone(Lead.objects.get(name='Другой').visitor)

    def test_crm_requires_permissions_and_shows_real_day_month_year_totals(self):
        self.client.get('/')
        self.client.post('/events/consent/', {'choice': 'allow'})
        self.client.post('/events/', {'id': uuid4(), 'kind': 'click', 'target': '#products', 'label': 'Каталог'})
        self.client.post('/', {'name': 'Клиент из Иваново', 'phone': '000'})
        self.assertIn('/crm/login/', self.client.get('/crm/').url)
        self.assertTemplateUsed(self.client.get('/crm/login/'), 'landing/office/login.html')
        user = get_user_model().objects.create_user('manager', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/crm/').status_code, 403)
        grant(user, 'landing', 'view_lead', 'view_trafficevent')
        dashboard = self.client.get('/crm/')
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Клиент из Иваново')
        self.assertContains(dashboard, '#products')
        self.assertEqual([(c['visitors'], c['clicks']) for c in dashboard.context['cards']], [(1, 1)] * 3)
        previous = self.client.get('/crm/', {'period': 'year', 'date': '01.03.2000'})
        self.assertEqual(previous.context['cards'][2]['visitors'], 0)
        history = self.client.get('/crm/', {'visitor': str(Lead.objects.get().visitor), 'date': '2000-03-01'})
        self.assertEqual(len(history.context['events']), 2)
        record = reverse('landing:lead_detail', args=[Lead.objects.get().pk])
        self.assertContains(self.client.get('/crm/leads/'), record)
        self.assertContains(self.client.get(record), 'Данные клиента')
        edit = {'status': 'active', 'note': 'Принято в работу', 'revision': 0}
        self.assertEqual(self.client.post(record, edit).status_code, 403)
        grant(user, 'landing', 'change_lead')
        self.assertEqual(self.client.post(record, edit).status_code, 302)
        self.assertEqual(self.client.post(record, {**edit, 'status': 'done'}).status_code, 409)
        self.assertEqual(Lead.objects.get().status, 'active')
        self.assertContains(self.client.get('/crm/leads/', {'q': 'несуществующий'}), 'Заявок нет')

    def test_chart_buckets_use_moscow_first_visit(self):
        zone = ZoneInfo('Europe/Moscow')
        returning, new = uuid4(), uuid4()
        for who, when in [(returning, datetime(2024, 2, 28, 23, 59, tzinfo=zone)),
                          (new, datetime(2024, 2, 29, 0, 1, tzinfo=zone)),
                          (returning, datetime(2024, 2, 29, 5, 0, tzinfo=zone))]:
            TrafficEvent.objects.create(visitor=who, created_at=when, kind='view', event_id=uuid4())
        migration = import_module('landing.migrations.0002_firstvisit_lead_revision')
        migration.backfill_first_visits(apps, connection.schema_editor())
        self.assertEqual(FirstVisit.objects.get(visitor=returning).first_seen.day, 28)
        staff = get_user_model().objects.create_user('analyst', is_staff=True)
        grant(staff, 'landing', 'view_lead', 'view_trafficevent')
        self.client.force_login(staff)
        for period, size, index, count in [('day', 24, 0, 1), ('month', 29, 28, 1), ('year', 12, 1, 2)]:
            response = self.client.get('/crm/', {'date': '29.02.2024', 'period': period})
            self.assertContains(response, '29.02.2024')
            self.assertEqual(len(response.context['bars']), size)
            self.assertEqual(response.context['bars'][index]['count'], count)
            self.assertEqual([card['visitors'] for card in response.context['cards']], [1, 2, 2])

    @override_settings(ALLOWED_HOSTS=['th37.ru', 'staging.th37.ru', 'testserver'])
    def test_public_search_metadata_matches_the_business_and_sitemap(self):
        public = Client(HTTP_HOST='th37.ru')
        home = public.get('/', secure=True)
        html = home.content.decode()
        self.assertContains(home, '<title>Купить промышленную химию оптом г. Иваново</title>', html=True)
        self.assertContains(home, '<meta name="robots" content="all">', count=1, html=True)
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)[1])
        self.assertEqual(data['address']['addressLocality'], 'Иваново')
        self.assertIn('Москва', data['areaServed'])
        self.assertIn('href="https://th37.ru/"', html)
        home_keywords = re.search(r'<meta name="keywords" content="([^"]+)"', html)[1].split(', ')
        self.assertIn('Иваново химия', home_keywords)
        self.assertIn('купить промышленную химию оптом', home_keywords)
        path = reverse('landing:caustic')
        self.assertIn(f'<a href="{path}">Каустическая сода (едкий натр)</a>', html)
        product = public.get(path, secure=True)
        self.assertContains(product, '<title>Каустическая сода купить оптом в Иваново</title>', html=True)
        self.assertContains(product, '<meta name="robots" content="all">', count=1, html=True)
        self.assertContains(product, '<h1>Каустическая сода оптом в Иваново</h1>')
        self.assertContains(product, f'<link rel="canonical" href="https://th37.ru{path}">', html=True)
        self.assertContains(product, 'href="/#contact"')
        product_keywords = re.search(r'<meta name="keywords" content="([^"]+)"', product.content.decode())[1].split(', ')
        self.assertIn('Иваново каустик', product_keywords)
        self.assertIn('сода каустическая оптом', product_keywords)
        for url in ('/', path):
            staging = self.client.get(url, secure=True, HTTP_HOST='staging.th37.ru')
            self.assertNotContains(staging, '<meta name="robots" content="all">', html=True)
        breadcrumbs = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', product.content.decode(), re.S)[1])
        self.assertEqual(breadcrumbs['itemListElement'][-1]['item'], 'https://th37.ru' + path)
        self.assertContains(self.client.get('/robots.txt'), 'Sitemap: https://th37.ru/sitemap.xml')
        root = ElementTree.fromstring(self.client.get('/sitemap.xml').content)
        self.assertCountEqual([el.text for el in root.findall('.//{*}loc')], ['https://th37.ru/', 'https://th37.ru' + path])
        key_path = reverse('landing:indexnow_key')
        key = self.client.get(key_path)
        self.assertEqual(key['Content-Type'], 'text/plain; charset=utf-8')
        self.assertEqual(key_path, '/' + key.content.decode() + '.txt')

    def test_consent_and_clicks_on_product_page(self):
        path = reverse('landing:caustic')
        self.assertContains(self.client.get(path), f'name="page" value="{path}"')
        self.assertFalse(FirstVisit.objects.exists())
        result = self.client.post('/events/consent/', {'choice': 'allow', 'page': path})
        self.assertRedirects(result, path)
        self.assertEqual(TrafficEvent.objects.get(kind='view').target, path)
        for target in (path, '/#contact'):
            response = self.client.post('/events/', {'kind': 'click', 'id': uuid4(), 'target': target})
            self.assertEqual(response.status_code, 204)
        self.assertEqual(FirstVisit.objects.count(), 1)
        self.assertEqual(TrafficEvent.objects.filter(kind='click').count(), 2)
        result = self.client.post('/events/consent/', {'choice': 'deny', 'page': 'https://example.org/'})
        self.assertRedirects(result, '/')

    def test_phone_format_for_new_leads(self):
        for value in ('9109854120', '8 (910) 985 41 20', '+7-910-985-41-20', '+375 29 123 45 67'):
            self.client.post('/', {'name': 'Клиент', 'phone': value})
            expected = value if value.startswith('+375') else '+7 (910) 985-41-20'
            self.assertEqual(Lead.objects.latest('pk').phone, expected)
        response = self.client.post('/', {'name': 'Клиент', 'phone': '+7 ('})
        self.assertContains(response, 'Введите номер телефона.')
        self.assertEqual(Lead.objects.count(), 4)


@override_settings(STORAGES=STATIC, PUBLIC_REVIEWS=True)
class ReviewTests(TestCase):
    databases = {'default', 'reviews'}

    def test_unlimited_submissions_and_manual_publication(self):
        guest = Client()
        data = {'form_kind': 'review', 'review-name': 'Гость', 'review-rating': 4,
                'review-comment': 'Получили документы', 'review-submission_id': str(uuid4())}
        page = guest.get('/')
        self.assertContains(page, 'Оставить отзыв')
        self.assertNotContains(page, 'Отзыв появится после одобрения модератором.')
        self.assertNotContains(page, 'name="review-review_date"')
        self.assertEqual(guest.post('/', {**data, 'review-rating': 6}).status_code, 200)
        self.assertFalse(Review.objects.exists())
        with patch('landing.views.timezone.now', return_value=datetime(2024, 2, 28, 22, 30, tzinfo=UTC)):
            for _ in range(2):
                response = guest.post('/', {**data, 'review-review_date': '31.12.2099', 'status': 'approved'})
                self.assertRedirects(response, '/#reviews', fetch_redirect_response=False)
        first = Review.objects.get()
        self.assertEqual((first.review_date, first.status), (date(2024, 2, 29), Review.Status.PENDING))
        second = {**data, 'review-submission_id': str(uuid4()), 'review-comment': 'Вторая отправка'}
        guest.post('/', second)
        self.assertEqual(Review.objects.count(), 2)
        self.assertNotContains(guest.get('/'), data['review-comment'])
        self.assertFalse(FirstVisit.objects.exists())

        moderate = reverse('landing:moderate', args=[first.pk])
        self.assertIn('/crm/login/', guest.post(moderate).url)
        staff = get_user_model().objects.create_user('Nick', is_staff=True)
        grant(staff, 'reviews', 'view_review')
        self.client.force_login(staff)
        self.assertContains(self.client.get('/crm/reviews/'), '29.02.2024')
        self.assertEqual(self.client.post(moderate, {'status': 'approved', 'revision': 0}).status_code, 403)
        grant(staff, 'reviews', 'change_review')
        self.assertEqual(self.client.post(moderate, {'status': 'approved', 'revision': 0}).status_code, 302)
        published = guest.get('/')
        self.assertContains(published, data['review-comment'])
        self.assertContains(published, '★★★★☆')
        self.assertNotContains(published, second['review-comment'])
        self.client.post(moderate, {'status': 'rejected', 'revision': 0})
        first.refresh_from_db()
        self.assertEqual((first.status, first.moderated_by), ('approved', 'Nick'))
        self.client.post(moderate, {'status': 'rejected', 'revision': 1})
        self.assertNotContains(guest.get('/'), data['review-comment'])

    def test_manager_can_publish_once_with_a_chosen_date(self):
        url = reverse('landing:create_review')
        guest = Client()
        self.assertIn('/crm/login/', guest.get(url).url)
        staff = get_user_model().objects.create_user('Nick', is_staff=True)
        grant(staff, 'reviews', 'view_review', 'change_review')
        self.client.force_login(staff)
        self.assertNotContains(self.client.get('/crm/reviews/'), 'Написать отзыв')
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        grant(staff, 'reviews', 'add_review')
        self.assertContains(self.client.get('/crm/reviews/'), url)
        form = self.client.get(url).context['review_form']
        data = {'review-submission_id': str(form['submission_id'].value()), 'review-name': 'Автор',
                'review-rating': '5', 'review-comment': 'Текст из кабинета', 'review-review_date': '31.12.2099'}
        self.assertContains(self.client.post(url, {**data, 'review-review_date': '31.02.2024'}), 'Введите дату')
        self.assertEqual(Review.objects.count(), 0)
        for _ in range(2):
            self.assertEqual(self.client.post(url, data).status_code, 302)
        review = Review.objects.get()
        self.assertEqual((review.status, review.moderated_by, review.review_date),
                         (Review.Status.APPROVED, 'Nick', date(2099, 12, 31)))
        self.assertEqual(review.moderated_at, review.submitted_at)
        self.assertContains(guest.get('/'), 'Текст из кабинета')
        self.assertContains(guest.get('/'), '<time datetime="2099-12-31">31.12.2099</time>', html=True)
        self.client.post(reverse('landing:moderate', args=[review.pk]), {'status': 'rejected', 'revision': 0})
        self.client.post(url, data)
        self.assertNotContains(guest.get('/'), 'Текст из кабинета')
        pending = {'form_kind': 'review', **data, 'review-submission_id': str(uuid4()), 'review-comment': 'От гостя'}
        guest.post('/', pending)
        self.client.post(url, pending)
        self.assertEqual(Review.objects.get(submission_id=pending['review-submission_id']).status, Review.Status.PENDING)

    @override_settings(PUBLIC_REVIEWS=False)
    def test_review_submissions_require_public_reviews_to_be_enabled(self):
        self.assertNotContains(self.client.get('/'), 'Оставить отзыв')
        self.assertEqual(self.client.post('/', {'form_kind': 'review'}).status_code, 404)
