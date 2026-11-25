import json
import re
from datetime import datetime
from importlib import import_module
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

    def test_public_search_metadata_matches_the_business_and_sitemap(self):
        html = self.client.get('/').content.decode()
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)[1])
        self.assertEqual(data['address']['addressLocality'], 'Иваново')
        self.assertIn('Москва', data['areaServed'])
        self.assertIn('href="https://th37.ru/"', html)
        self.assertContains(self.client.get('/robots.txt'), 'Sitemap: https://th37.ru/sitemap.xml')
        root = ElementTree.fromstring(self.client.get('/sitemap.xml').content)
        self.assertEqual([el.text for el in root.findall('.//{*}loc')], ['https://th37.ru/'])


@override_settings(STORAGES=STATIC, PUBLIC_REVIEWS=True)
class ReviewTests(TestCase):
    databases = {'default', 'reviews'}

    def test_unlimited_submissions_and_manual_publication(self):
        guest = Client()
        data = {'form_kind': 'review', 'review-name': 'Гость', 'review-rating': 4, 'review-review_date': '29.02.2024',
                'review-comment': 'Получили документы', 'review-submission_id': str(uuid4())}
        self.assertContains(guest.get('/'), 'Оставить отзыв')
        self.assertContains(guest.post('/', {**data, 'review-review_date': '2024-02-29'}), 'Введите дату')
        self.assertContains(guest.post('/', {**data, 'review-review_date': '31.02.2024'}), 'Введите дату')
        self.assertEqual(guest.post('/', {**data, 'review-rating': 6}).status_code, 200)
        self.assertFalse(Review.objects.exists())
        for _ in range(2):
            self.assertRedirects(guest.post('/', data), '/#reviews', fetch_redirect_response=False)
        first = Review.objects.get()
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

    @override_settings(PUBLIC_REVIEWS=False)
    def test_review_submissions_are_staging_only(self):
        self.assertNotContains(self.client.get('/'), 'Оставить отзыв')
        self.assertEqual(self.client.post('/', {'form_kind': 'review'}).status_code, 404)
