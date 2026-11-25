from django.db import models
from django.utils import timezone


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        ACTIVE = 'active', 'В работе'
        DONE = 'done', 'Обработана'

    submission_id = models.UUIDField(unique=True, editable=False)
    visitor = models.UUIDField('Посетитель', null=True, blank=True, db_index=True, editable=False)
    created_at = models.DateTimeField('Получена', default=timezone.now, db_index=True)
    name = models.CharField('Имя', max_length=120)
    phone = models.CharField('Телефон', max_length=40)
    cargo = models.CharField('Продукция', max_length=200, blank=True)
    comment = models.TextField('Сообщение клиента', blank=True)
    status = models.CharField('Статус', max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)
    note = models.TextField('Заметка менеджера', blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'заявка'
        verbose_name_plural = 'заявки'

    def __str__(self):
        return f'Заявка №{self.pk} · {self.name}'


class FirstVisit(models.Model):
    visitor = models.UUIDField(primary_key=True)
    first_seen = models.DateTimeField(db_index=True, default=timezone.now)


class TrafficEvent(models.Model):
    class Kind(models.TextChoices):
        VIEW = 'view', 'Просмотр'
        CLICK = 'click', 'Клик'

    event_id = models.UUIDField(unique=True, editable=False)
    visitor = models.UUIDField('Посетитель', db_index=True)
    created_at = models.DateTimeField('Время', default=timezone.now, db_index=True)
    kind = models.CharField('Событие', max_length=8, choices=Kind.choices)
    placement = models.CharField('Раздел', max_length=32, blank=True)
    label = models.CharField('Элемент', max_length=128, blank=True)
    target = models.CharField('Назначение', max_length=200, blank=True)
    source = models.CharField('Источник перехода', max_length=253, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = 'событие'
        verbose_name_plural = 'события'
