from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

from .models import Lead, TrafficEvent


@permission_required(['landing.view_lead', 'landing.view_trafficevent'], raise_exception=True)
def dashboard(request):
    try:
        day = date.fromisoformat(request.GET['date']) if request.GET.get('date') else timezone.localdate()
        visitor = UUID(request.GET['visitor']) if request.GET.get('visitor') else None
    except ValueError:
        return HttpResponseBadRequest('Некорректная дата или идентификатор посетителя.')
    if not 2000 <= day.year <= 9900:
        return HttpResponseBadRequest('Дата вне допустимого диапазона.')

    month = day.replace(day=1)
    next_month = (month + timedelta(days=32)).replace(day=1)
    periods = {
        'day': ('День', day, day + timedelta(days=1)),
        'month': ('Месяц', month, next_month),
        'year': ('Год', date(day.year, 1, 1), date(day.year + 1, 1, 1)),
    }
    selected = request.GET.get('period', 'day')
    if selected not in periods:
        selected = 'day'
    cards = []
    for key, (label, start, end) in periods.items():
        lower = timezone.make_aware(datetime.combine(start, time.min))
        upper = timezone.make_aware(datetime.combine(end, time.min))
        events = TrafficEvent.objects.filter(created_at__gte=lower, created_at__lt=upper)
        cards.append({'key': key, 'label': label, **events.aggregate(
            views=Count('pk', filter=Q(kind='view')), visitors=Count('visitor', distinct=True),
            clicks=Count('pk', filter=Q(kind='click')),
        )})
        if key == selected:
            period_events = events

    if visitor:
        history = TrafficEvent.objects.filter(visitor=visitor)
    else:
        history = period_events
    page = Paginator(history, 30).get_page(request.GET.get('page'))
    rows = list(page.object_list)
    names = {}
    for lead in Lead.objects.filter(visitor__in={row.visitor for row in rows}).values('visitor', 'name'):
        names.setdefault(lead['visitor'], lead['name'])
    for row in rows:
        row.visitor_label = names.get(row.visitor) or f'Гость {str(row.visitor)[:8]}'
    return render(request, 'landing/crm.html', {
        'date': day.isoformat(), 'cards': cards, 'period': selected, 'visitor': visitor,
        'page': page, 'events': rows, 'leads': Lead.objects.all()[:10],
        'new_count': Lead.objects.filter(status=Lead.Status.NEW).count(),
    })
