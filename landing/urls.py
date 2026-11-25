from django.urls import path
from django.contrib import admin

from . import crm, traffic, views

app_name = 'landing'

urlpatterns = [
    path('', views.index, name='index'),
    path('robots.txt', views.robots, name='robots'),
    path('sitemap.xml', views.sitemap, name='sitemap'),
    path('events/', traffic.record, name='events'),
    path('crm/', admin.site.admin_view(crm.dashboard), name='crm'),
]
