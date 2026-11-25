from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'name', 'phone', 'cargo', 'status')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'phone', 'cargo', 'comment')
    fields = ('created_at', 'name', 'phone', 'cargo', 'comment', 'activity', 'status', 'note')
    readonly_fields = ('created_at', 'name', 'phone', 'cargo', 'comment', 'activity')

    @admin.display(description='История посетителя')
    def activity(self, obj):
        if obj.visitor:
            return format_html('<a href="{}?visitor={}">Открыть историю кликов</a>', reverse('landing:crm'), obj.visitor)
        return '—'


admin.site.site_header = 'Техснаб · CRM'
admin.site.site_title = 'Техснаб · CRM'
admin.site.site_url = '/crm/'
