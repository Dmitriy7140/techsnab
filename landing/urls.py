from django.urls import path
from django.contrib.auth.views import LogoutView
from django.views.generic import RedirectView
from django.urls import reverse_lazy

from . import crm, traffic, views

app_name = 'landing'

urlpatterns = [
    path('', views.index, name='index'),
    path('favicon.ico', views.favicon, name='favicon'),
    path('robots.txt', views.robots, name='robots'),
    path('sitemap.xml', views.sitemap, name='sitemap'),
    path('events/', traffic.record, name='events'),
    path('events/consent/', traffic.consent, name='consent'),
    path('crm/', crm.dashboard, name='crm'),
    path('crm/login/', crm.ManagerLogin.as_view(), name='crm_login'),
    path('crm/logout/', LogoutView.as_view(next_page=reverse_lazy('landing:crm_login')), name='crm_logout'),
    path('crm/leads/', crm.leads, name='crm_leads'),
    path('crm/leads/<int:pk>/', crm.lead_detail, name='lead_detail'),
    path('crm/reviews/', crm.reviews, name='crm_reviews'),
    path('crm/reviews/new/', crm.create_review, name='create_review'),
    path('crm/reviews/<int:pk>/moderate/', crm.moderate, name='moderate'),
    path('admin/', RedirectView.as_view(pattern_name='landing:crm')),
    path('admin/login/', RedirectView.as_view(pattern_name='landing:crm_login')),
    path('admin/landing/lead/', RedirectView.as_view(pattern_name='landing:crm_leads')),
    path('admin/landing/lead/<int:pk>/change/', RedirectView.as_view(pattern_name='landing:lead_detail')),
]
