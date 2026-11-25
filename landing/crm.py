from calendar import monthrange
from datetime import date, datetime, time, timedelta
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import permission_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.db.models.functions import ExtractDay, ExtractHour, ExtractMonth
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .forms import LeadUpdateForm, ManagerLoginForm, ManagerReviewForm, RussianDateField
from .models import FirstVisit, Lead, TrafficEvent
from .reviews.models import Review


class ManagerLogin(LoginView):
    authentication_form = ManagerLoginForm
    template_name = 'landing/office/login.html'
    next_page = reverse_lazy('landing:crm')
    redirect_authenticated_user = False


def manager_access(*permissions):
    def decorate(view):
        protected = permission_required(permissions, raise_exception=True)(view)
        staff_only = user_passes_test(lambda user: user.is_active and user.is_staff, login_url='landing:crm_login')
        return never_cache(staff_only(protected))
    return decorate


def _midnight(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _chart(visits, period, day):
    if period == 'day':
        parts, extract = range(24), ExtractHour('first_seen')
        labels = [f'{hour:02d}:00' for hour in parts]
        descriptions = [f'{day:%d.%m.%Y} {label}' for label in labels]
    elif period == 'month':
        parts, extract = range(1, monthrange(day.year, day.month)[1] + 1), ExtractDay('first_seen')
        labels = [f'{n:02d}' for n in parts]
        descriptions = [f'{day.replace(day=n):%d.%m.%Y}' for n in parts]
    else:
        parts, extract = range(1, 13), ExtractMonth('first_seen')
        labels = 'янв фев мар апр май июн июл авг сен окт ноя дек'.split()
        descriptions = [f'{date(day.year,n,1):%d.%m.%Y} – {date(day.year,n,monthrange(day.year,n)[1]):%d.%m.%Y}' for n in parts]
    values = dict(visits.order_by().annotate(bucket=extract).values('bucket').annotate(n=Count('pk')).values_list('bucket', 'n'))
    maximum = max(1, max(values.values(), default=0))
    bars = []
    for i, (part, label, description) in enumerate(zip(parts, labels, descriptions)):
        count = values.get(part, 0)
        bars.append({'label': label, 'description': description, 'count': count,
                     'height': round(100 * count / maximum), 'tick': i % (2 if period == 'year' else 4) == 0 or i == len(parts) - 1})
    return bars, maximum


@manager_access('landing.view_lead', 'landing.view_trafficevent')
def dashboard(request):
    raw_date = request.GET.get('date')
    try:
        if raw_date and '-' in raw_date:  # Older bookmarked filters use ISO dates.
            day = date.fromisoformat(raw_date)
        else:
            day = RussianDateField().clean(raw_date) if raw_date else timezone.localdate()
        visitor = UUID(request.GET['visitor']) if request.GET.get('visitor') else None
    except (ValueError, ValidationError):
        return HttpResponseBadRequest('Введите корректную дату в формате дд.мм.гггг или идентификатор посетителя.')
    if not 1 <= day.year < 9999:
        return HttpResponseBadRequest('Дата вне допустимого диапазона.')
    month = day.replace(day=1)
    periods = {
        'day': ('День', day, day + timedelta(days=1)),
        'month': ('Месяц', month, (month + timedelta(days=32)).replace(day=1)),
        'year': ('Год', date(day.year, 1, 1), date(day.year + 1, 1, 1)),
    }
    selected = request.GET.get('period', 'day')
    if selected not in periods:
        selected = 'day'
    cards = []
    for key, (label, start, end) in periods.items():
        lower, upper = _midnight(start), _midnight(end)
        visits = FirstVisit.objects.filter(first_seen__gte=lower, first_seen__lt=upper)
        events = TrafficEvent.objects.filter(created_at__gte=lower, created_at__lt=upper)
        cards.append({'key': key, 'label': label, 'visitors': visits.count(), 'clicks': events.filter(kind='click').count()})
        if key == selected:
            graph, maximum = _chart(visits, key, day)
            period_events = events
    history = TrafficEvent.objects.filter(visitor=visitor) if visitor else period_events
    page = Paginator(history, 30).get_page(request.GET.get('page'))
    rows = list(page.object_list)
    names = {}
    for lead in Lead.objects.filter(visitor__in={row.visitor for row in rows}).values('visitor', 'name'):
        names.setdefault(lead['visitor'], lead['name'])
    for row in rows:
        row.visitor_label = names.get(row.visitor) or f'Гость {str(row.visitor)[:8]}'
    return render(request, 'landing/crm.html', {
        'section': 'traffic', 'date': day.strftime('%d.%m.%Y'), 'cards': cards, 'period': selected, 'visitor': visitor,
        'bars': graph, 'maximum': maximum, 'page': page, 'events': rows,
        'leads': Lead.objects.all()[:5], 'new_count': Lead.objects.filter(status=Lead.Status.NEW).count(),
    })


@manager_access('landing.view_lead')
def leads(request):
    status, query = request.GET.get('status', ''), request.GET.get('q', '').strip()
    records = Lead.objects.all()
    if status in Lead.Status.values:
        records = records.filter(status=status)
    if query:
        records = records.filter(Q(name__icontains=query) | Q(phone__icontains=query) | Q(cargo__icontains=query) | Q(comment__icontains=query))
    page = Paginator(records, 25).get_page(request.GET.get('page'))
    return render(request, 'landing/office/leads.html', {'section': 'leads', 'leads': page.object_list, 'page': page,
                  'statuses': Lead.Status.choices, 'status': status, 'q': query})


@manager_access('landing.view_lead')
def lead_detail(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    form = LeadUpdateForm(request.POST if request.method == 'POST' else None, instance=lead)
    code = 200
    if request.method == 'POST':
        if not request.user.has_perm('landing.change_lead'):
            raise PermissionDenied
        if form.is_valid():
            data = form.cleaned_data
            updated = Lead.objects.filter(pk=pk, revision=data['revision']).update(
                status=data['status'], note=data['note'], revision=F('revision') + 1)
            if updated:
                messages.success(request, 'Изменения сохранены.')
                return redirect('landing:lead_detail', pk=pk)
            lead.refresh_from_db()
            form.add_error(None, 'Заявку уже изменили. Обновите страницу перед сохранением.')
            code = 409
    return render(request, 'landing/office/lead.html', {'section': 'leads', 'lead': lead, 'form': form}, status=code)


@manager_access('reviews.view_review')
def reviews(request):
    status = request.GET.get('status', Review.Status.PENDING)
    if status not in Review.Status.values:
        status = Review.Status.PENDING
    page = Paginator(Review.objects.filter(status=status), 20).get_page(request.GET.get('page'))
    counts = dict(Review.objects.order_by().values('status').annotate(n=Count('pk')).values_list('status', 'n'))
    tabs = [(key, label, counts.get(key, 0)) for key, label in Review.Status.choices]
    return render(request, 'landing/office/reviews.html', {'section': 'reviews', 'page': page, 'status': status, 'tabs': tabs})


@manager_access('reviews.view_review', 'reviews.add_review', 'reviews.change_review')
@require_http_methods(['GET', 'POST'])
def create_review(request):
    form = ManagerReviewForm(request.POST if request.method == 'POST' else None, prefix='review')
    if request.method == 'POST' and form.is_valid():
        now = timezone.now()
        review, created = form.save(
            submitted_at=now, review_date=form.cleaned_data['review_date'], status=Review.Status.APPROVED,
            moderated_at=now, moderated_by=request.user.get_username(),
        )
        if created:
            messages.success(request, 'Отзыв опубликован.')
        else:
            messages.info(request, 'Этот отзыв уже сохранён.')
        return redirect(f"{reverse('landing:crm_reviews')}?status={review.status}#review-{review.pk}")
    return render(request, 'landing/office/create_review.html', {'section': 'reviews', 'review_form': form})


@manager_access('reviews.view_review', 'reviews.change_review')
@require_POST
def moderate(request, pk):
    choice = request.POST.get('status')
    if choice not in (Review.Status.APPROVED, Review.Status.REJECTED):
        return HttpResponseBadRequest('Неизвестное решение.')
    try:
        revision = forms.IntegerField(min_value=0).clean(request.POST.get('revision'))
    except ValidationError:
        return HttpResponseBadRequest('Некорректная версия отзыва.')
    review = get_object_or_404(Review, pk=pk)
    changed = Review.objects.filter(pk=pk, revision=revision).update(
        status=choice, moderated_at=timezone.now(), moderated_by=request.user.get_username(), revision=F('revision') + 1)
    if not changed:
        messages.error(request, 'Решение по отзыву уже изменилось. Проверьте его текущий статус.')
    else:
        messages.success(request, 'Отзыв опубликован.' if choice == Review.Status.APPROVED else 'Отзыв отклонён.')
    return redirect(f"{reverse_lazy('landing:crm_reviews')}?status={review.status}")
