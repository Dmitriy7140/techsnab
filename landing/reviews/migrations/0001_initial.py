import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submission_id', models.UUIDField(editable=False, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('rating', models.PositiveSmallIntegerField()),
                ('comment', models.TextField()),
                ('review_date', models.DateField()),
                ('submitted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.CharField(choices=[('pending', 'На модерации'), ('approved', 'Опубликован'), ('rejected', 'Отклонён')], db_index=True, default='pending', max_length=10)),
                ('moderated_at', models.DateTimeField(null=True)),
                ('moderated_by', models.CharField(blank=True, max_length=150)),
                ('revision', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['-submitted_at', '-pk'],
                'constraints': [models.CheckConstraint(condition=models.Q(('rating__range', (1, 5))), name='review_rating_1_to_5')],
            },
        ),
    ]
