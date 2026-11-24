from django.db import migrations, models


def backfill_checked_threads(apps, schema_editor):
    # Only historical explicit notify-all notifications are evidence of consent.
    Notification = apps.get_model('notifications', 'Notification')
    BroadcastThread = apps.get_model('limes_notification_policy', 'BroadcastThread')
    database = schema_editor.connection.alias
    rows = Notification.objects.using(database).filter(
        notification_type='new_instructor_all_learners_post',
    ).values_list('course_id', 'content_context', 'content_url').iterator(chunk_size=500)
    for course_id, context, url in rows:
        thread_id = context.get('thread_id')
        if not thread_id and '/posts/' in url:
            thread_id = url.split('/posts/', 1)[1].split('?', 1)[0].strip('/')
        if thread_id and '/' not in str(thread_id):
            BroadcastThread.objects.using(database).get_or_create(
                course_id=str(course_id), thread_id=str(thread_id),
            )


class Migration(migrations.Migration):
    dependencies = [('limes_notification_policy', '0001_immediate_email_defaults')]
    operations = [
        migrations.CreateModel(
            name='BroadcastThread',
            fields=[('id', models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                    ('course_id', models.CharField(max_length=255)),
                    ('thread_id', models.CharField(max_length=255))],
            options={'unique_together': {('course_id', 'thread_id')}},
        ),
        migrations.RunPython(backfill_checked_threads, migrations.RunPython.noop),
    ]
