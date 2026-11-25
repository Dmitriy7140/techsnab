import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submission_id', models.UUIDField(editable=False, unique=True)),
                ('visitor', models.UUIDField(blank=True, db_index=True, editable=False, null=True, verbose_name='Посетитель')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Получена')),
                ('name', models.CharField(max_length=120, verbose_name='Имя')),
                ('phone', models.CharField(max_length=40, verbose_name='Телефон')),
                ('cargo', models.CharField(blank=True, max_length=200, verbose_name='Продукция')),
                ('comment', models.TextField(blank=True, verbose_name='Сообщение клиента')),
                ('status', models.CharField(choices=[('new', 'Новая'), ('active', 'В работе'), ('done', 'Обработана')], db_index=True, default='new', max_length=12, verbose_name='Статус')),
                ('note', models.TextField(blank=True, verbose_name='Заметка менеджера')),
            ],
            options={
                'verbose_name': 'заявка',
                'verbose_name_plural': 'заявки',
                'ordering': ['-created_at', '-pk'],
            },
        ),
        migrations.CreateModel(
            name='TrafficEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.UUIDField(editable=False, unique=True)),
                ('visitor', models.UUIDField(db_index=True, verbose_name='Посетитель')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Время')),
                ('kind', models.CharField(choices=[('view', 'Просмотр'), ('click', 'Клик')], max_length=8, verbose_name='Событие')),
                ('placement', models.CharField(blank=True, max_length=32, verbose_name='Раздел')),
                ('label', models.CharField(blank=True, max_length=128, verbose_name='Элемент')),
                ('target', models.CharField(blank=True, max_length=200, verbose_name='Назначение')),
                ('source', models.CharField(blank=True, max_length=253, verbose_name='Источник перехода')),
            ],
            options={
                'verbose_name': 'событие',
                'verbose_name_plural': 'события',
                'ordering': ['-created_at', '-pk'],
            },
        ),
    ]
