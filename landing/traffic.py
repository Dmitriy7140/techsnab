from uuid import UUID
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from .models import TrafficEvent


def visitor_id(request):
    value = request.get_signed_cookie('th37_visitor', default='', salt='traffic')
    try:
        return UUID(value)
    except ValueError:
        return None


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
        try:
            source = urlsplit(data.get('referrer', '')).hostname or ''
        except ValueError:
            source = ''
        details = {'source': source[:253], 'target': '/'}
    elif kind == TrafficEvent.Kind.CLICK:
        site = settings.SITE
        targets = {
            '#products', '#how', '#why', '#contact', '#top', 'menu', 'request-form',
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
