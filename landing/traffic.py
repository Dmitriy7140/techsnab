from uuid import UUID, uuid4
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_POST

from .models import FirstVisit, TrafficEvent

COOKIE_AGE = 365 * 24 * 60 * 60


def consent_state(request):
    if request.headers.get('DNT') == '1' or request.headers.get('Sec-GPC') == '1':
        return 'private'
    state = request.get_signed_cookie('th37_consent', default='', salt='analytics-choice')
    return '' if state == 'allow' and _stored_visitor(request) is None else state


def _stored_visitor(request):
    value = request.get_signed_cookie('th37_visitor', default='', salt='traffic')
    try:
        return UUID(value)
    except ValueError:
        return None


def visitor_id(request):
    return _stored_visitor(request) if consent_state(request) == 'allow' else None


@require_POST
def consent(request):
    choice = request.POST.get('choice')
    if choice not in ('allow', 'deny'):
        return HttpResponseBadRequest()
    if consent_state(request) == 'private':
        choice = 'deny'
    page = request.POST.get('page')
    if page not in (reverse('landing:index'), reverse('landing:caustic')):
        page = reverse('landing:index')
    response = HttpResponse(status=204) if request.headers.get('Accept') == 'application/json' else redirect(page)
    options = {'max_age': COOKIE_AGE, 'secure': request.is_secure(), 'httponly': True, 'samesite': 'Lax'}
    response.set_signed_cookie('th37_consent', choice, salt='analytics-choice', **options)
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Analytics-Choice'] = choice
    if choice == 'deny':
        response.delete_cookie('th37_visitor', samesite='Lax')
        return response
    visitor = _stored_visitor(request)
    if visitor is None:
        # Concurrent approvals from tabs sharing a CSRF cookie must count only once.
        get_token(request)
        seed = request.META['CSRF_COOKIE'] + timezone.localdate().isoformat()
        visitor = UUID(bytes=salted_hmac('analytics-consent', seed, algorithm='sha256').digest()[:16], version=4)
        try:
            source = urlsplit(request.POST.get('referrer', '')).hostname or ''
        except ValueError:
            source = ''
        with transaction.atomic():
            _, first = FirstVisit.objects.get_or_create(visitor=visitor)
            if first:
                TrafficEvent.objects.create(event_id=uuid4(), kind='view', visitor=visitor, source=source[:253], target=page)
    response.set_signed_cookie('th37_visitor', str(visitor), salt='traffic', **options)
    return response


@require_POST
def record(request):
    visitor = visitor_id(request)
    if visitor is None:
        return HttpResponse(status=204)
    data = request.POST
    try:
        event_id = UUID(data.get('id', ''))
    except ValueError:
        return HttpResponseBadRequest()
    kind = data.get('kind')
    if kind == TrafficEvent.Kind.VIEW:
        return HttpResponse(status=204)
    if kind == TrafficEvent.Kind.CLICK:
        site = settings.SITE
        targets = {
            reverse('landing:caustic'), '/', '/#products', '/#contact',
            '#products', '#how', '#why', '#contact', '#reviews', '#top', 'menu', 'request-form', 'review-form', 'review-page',
            'tel:' + site['phone_href'], 'tel:' + site['phone_city_href'], 'mailto:' + site['email'],
            'https://commons.wikimedia.org/?curid=78303301', 'https://creativecommons.org/licenses/by/2.0/',
        }
        if data.get('target') not in targets:
            return HttpResponseBadRequest()
        details = {'label': data.get('label', '')[:128], 'placement': data.get('placement', '')[:32],
                   'target': data['target']}
    else:
        return HttpResponseBadRequest()
    TrafficEvent.objects.get_or_create(event_id=event_id, defaults={'kind': kind, 'visitor': visitor, **details})
    return HttpResponse(status=204)
