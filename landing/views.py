from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.shortcuts import redirect, render
from django.templatetags.static import static

from .forms import RequestForm, ReviewForm
from .models import Lead
from .reviews.models import Review
from .traffic import consent_state, visitor_id

# Каталог продукции — наименование, формула/маркировка, применение.
PRODUCTS = [
    {
        'icon': 'drop', 'name': 'Каустическая сода (едкий натр)', 'formula': 'NaOH', 'page': 'landing:caustic',
        'use': 'Для целлюлозно-бумажной, химической и нефтяной промышленности, водоподготовки.',
    },
    {
        'icon': 'flask', 'name': 'Перекись водорода', 'formula': 'H₂O₂',
        'use': 'Окислитель и отбеливатель для целлюлозы, текстиля и водоочистки.',
    },
    {
        'icon': 'acid', 'name': 'Кислота серная', 'formula': 'H₂SO₄',
        'use': 'Для химических производств, выпуска удобрений и водоочистки.',
    },
    {
        'icon': 'acid', 'name': 'Кислота соляная', 'formula': 'HCl',
        'use': 'Для металлообработки, нефтедобычи и химической промышленности.',
    },
    {
        'icon': 'drop', 'name': 'Аммиак водный', 'formula': 'NH₄OH',
        'use': 'Азотное удобрение и реагент для очистки промышленных газов.',
    },
    {
        'icon': 'box', 'name': 'Карбамид (мочевина)', 'formula': '(NH₂)₂CO',
        'use': 'Азотное удобрение, кормовая добавка и сырьё для смол.',
    },
    {
        'icon': 'box', 'name': 'Сульфат аммония', 'formula': '(NH₄)₂SO₄',
        'use': 'Азотно-серное удобрение и реагент для промышленности.',
    },
    {
        'icon': 'barrel', 'name': 'Крахмал кукурузный', 'formula': '',
        'use': 'Для пищевой, бумажной и текстильной промышленности.',
    },
    {
        'icon': 'snow', 'name': 'Сульфат натрия природный', 'formula': 'Na₂SO₄',
        'use': 'Для стекольной, моющей и целлюлозно-бумажной промышленности.',
    },
    {
        'icon': 'drop', 'name': 'Сульфат алюминия', 'formula': 'Al₂(SO₄)₃',
        'use': 'Коагулянт для водоподготовки, очистки сточных вод и в бумажной промышленности.',
    },
    {
        'icon': 'snow', 'name': 'Соль таблетированная', 'formula': 'NaCl',
        'use': 'Для водоподготовки и регенерации систем умягчения воды.',
    },
    {
        'icon': 'barrel', 'name': 'Гидросульфит натрия', 'formula': 'NaHSO₃',
        'use': 'Восстановитель и отбеливатель для текстиля и бумаги.',
    },
]

# Как мы работаем.
STEPS = [
    ('Заявка', 'Оставляете заявку или звоните. Уточняем продукцию, объём и адрес доставки.'),
    ('Расчёт', 'Готовим коммерческое предложение с фиксированной ценой и наличием.'),
    ('Документы', 'Оформляем договор и все сопроводительные документы на продукцию.'),
    ('Отгрузка', 'Подаём подходящий транспорт и отгружаем продукцию с контролем на маршруте.'),
    ('Доставка', 'Доставляем груз получателю вместе с закрывающими документами.'),
]

# Почему мы.
ADVANTAGES = [
    ('Профильный опыт', 'Работаем с химической продукцией более 20 лет. Знаем специфику каждого товара.'),
    ('Собственный парк', 'Специализированные цистерны и опытные водители для химических грузов.'),
    ('Документы и качество', 'Договор, паспорта качества и все сопроводительные документы на продукцию.'),
]

STATS = [
    ('20', 'лет на рынке химической продукции'),
    ('5 000+', 'успешно доставленных грузов'),
    ('12', 'позиций в каталоге продукции'),
]


def index(request):
    is_review = request.method == 'POST' and request.POST.get('form_kind') == 'review'
    if is_review and not settings.PUBLIC_REVIEWS:
        raise Http404
    form = RequestForm(initial={'submission_id': uuid4()})
    review_form = None
    published = None
    if settings.PUBLIC_REVIEWS:
        review_form = ReviewForm(request.POST if is_review else None, prefix='review')
        if is_review and review_form.is_valid():
            now = timezone.now()
            review_form.save(submitted_at=now, review_date=timezone.localdate(now))
            messages.success(request, 'Спасибо! Отзыв отправлен на модерацию.', extra_tags='review')
            return redirect(f'{request.path}#reviews')
        approved = Review.objects.filter(status=Review.Status.APPROVED).order_by('-review_date', '-pk')
        published = Paginator(approved, 6).get_page(request.GET.get('review_page'))
    if request.method == 'POST' and not is_review:
        form = RequestForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            Lead.objects.get_or_create(
                submission_id=data.get('submission_id') or uuid4(),
                defaults={**{key: data[key] for key in ('name', 'phone', 'cargo', 'comment')}, 'visitor': visitor_id(request)},
            )
            messages.success(
                request,
                'Спасибо! Заявка принята — мы свяжемся с вами в ближайшее время.',
            )
            return redirect(f"{request.path}#contact")

    context = {
        'form': form,
        'products': PRODUCTS,
        'steps': STEPS,
        'advantages': ADVANTAGES,
        'stats': STATS,
        'review_form': review_form,
        'published': published,
    }
    return public_page(request, 'landing/index.html', context)


def public_page(request, template, context=None):
    response = render(request, template, {
        'site': settings.SITE, 'consent_state': consent_state(request), **(context or {}),
    })
    response.headers['Cache-Control'] = 'private, no-store'
    return response


def caustic(request):
    return public_page(request, 'landing/caustic.html')


def robots(request):
    return HttpResponse(
        f"User-agent: *\nDisallow: /admin/\nDisallow: /crm/\nDisallow: /events/\n\nSitemap: {settings.SITE['url']}/sitemap.xml\n",
        content_type='text/plain; charset=utf-8',
    )


def sitemap(request):
    return render(request, 'landing/sitemap.xml', {'site': settings.SITE}, content_type='application/xml')


def favicon(request):
    return redirect(static('landing/img/favicon.ico'))
