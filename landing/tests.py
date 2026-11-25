import json
import re
from uuid import uuid4
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Lead, TrafficEvent


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class LandingTests(TestCase):
    def test_form_and_clicks_reach_the_same_visitor_history(self):
        page = self.client.get('/')
        ticket = page.context['form'].initial['submission_id']
        self.client.post('/', {'submission_id': ticket, 'name': 'Тест'})
        self.assertFalse(Lead.objects.exists())
        details = {'submission_id': ticket, 'name': 'Тест', 'phone': '000', 'cargo': 'Сода'}
        for _ in range(2):
            self.assertRedirects(self.client.post('/', details), '/#contact', fetch_redirect_response=False)
        lead = Lead.objects.get()
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertIsNotNone(lead.visitor)
        click = {'id': uuid4(), 'kind': 'click', 'target': '#contact', 'label': 'Рассчитать стоимость'}
        for _ in range(2):
            self.assertEqual(self.client.post('/events/', click).status_code, 204)
        self.assertEqual(TrafficEvent.objects.get().visitor, lead.visitor)
        self.assertEqual(self.client.post('/events/', {**click, 'target': 'https://unknown.example/'}).status_code, 400)
        self.assertEqual(self.client.post('/events/', {'id': uuid4(), 'kind': 'view', 'referrer': 'https://ref.example/private?q=x'}).status_code, 204)
        self.assertEqual(TrafficEvent.objects.get(kind='view').source, 'ref.example')
        self.assertEqual(Client(enforce_csrf_checks=True).post('/events/', click).status_code, 403)

    def test_crm_requires_permissions_and_shows_real_day_month_year_totals(self):
        self.client.get('/')
        self.client.post('/events/', {'id': uuid4(), 'kind': 'view'})
        self.client.post('/events/', {'id': uuid4(), 'kind': 'click', 'target': '#products', 'label': 'Каталог'})
        self.client.post('/', {'name': 'Клиент из Иваново', 'phone': '000'})
        self.assertEqual(self.client.get('/crm/').status_code, 302)
        user = get_user_model().objects.create_user('manager', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/crm/').status_code, 403)
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='landing', codename__in=['view_lead', 'change_lead', 'view_trafficevent']))
        dashboard = self.client.get('/crm/')
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Клиент из Иваново')
        self.assertContains(dashboard, '#products')
        self.assertEqual([(c['views'], c['visitors'], c['clicks']) for c in dashboard.context['cards']], [(1, 1, 1)] * 3)
        previous = self.client.get('/crm/', {'period': 'year', 'date': '2000-03-01'})
        self.assertEqual(previous.context['cards'][2]['views'], 0)
        history = self.client.get('/crm/', {'visitor': str(Lead.objects.get().visitor), 'date': '2000-03-01'})
        self.assertEqual(len(history.context['events']), 2)
        record = reverse('admin:landing_lead_change', args=[Lead.objects.get().pk])
        self.assertEqual(self.client.post(record, {'status': 'active', 'note': 'Принято в работу'}).status_code, 302)
        self.assertEqual(Lead.objects.get().status, 'active')

    def test_public_search_metadata_matches_the_business_and_sitemap(self):
        html = self.client.get('/').content.decode()
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)[1])
        self.assertEqual(data['address']['addressLocality'], 'Иваново')
        self.assertIn('Москва', data['areaServed'])
        self.assertIn('href="https://th37.ru/"', html)
        self.assertContains(self.client.get('/robots.txt'), 'Sitemap: https://th37.ru/sitemap.xml')
        root = ElementTree.fromstring(self.client.get('/sitemap.xml').content)
        self.assertEqual([el.text for el in root.findall('.//{*}loc')], ['https://th37.ru/'])
