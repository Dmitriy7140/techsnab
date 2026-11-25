import django.utils.timezone
from django.db import migrations, models


def backfill_first_visits(apps, schema_editor):
    events = apps.get_model('landing', 'TrafficEvent')
    first_visits = apps.get_model('landing', 'FirstVisit')
    quote = schema_editor.quote_name
    # One grouped insert preserves the original timestamp and needs no Python-side buffer.
    schema_editor.execute(
        f'INSERT INTO {quote(first_visits._meta.db_table)} (visitor, first_seen) '
        f'SELECT visitor, MIN(created_at) FROM {quote(events._meta.db_table)} GROUP BY visitor'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('landing', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FirstVisit',
            fields=[
                ('visitor', models.UUIDField(primary_key=True, serialize=False)),
                ('first_seen', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
        ),
        migrations.AddField(
            model_name='lead',
            name='revision',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_first_visits, migrations.RunPython.noop),
    ]
