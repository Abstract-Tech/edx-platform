# Apply defaults once; do not overwrite future preference changes.
from django.conf import settings
from django.db import migrations


# Freeze this rollout's scope. Staff-only ORA notifications retain upstream defaults.
TYPES_BY_APP = {
    "discussion": (
        "new_comment_on_response", "new_comment", "new_response",
        "new_discussion_post", "new_question_post", "response_on_followed_post",
        "comment_on_followed_post", "content_reported", "response_endorsed_on_thread",
        "response_endorsed", "new_instructor_all_learners_post",
    ),
    "updates": ("course_updates",),
    "grading": ("ora_grade_assigned", "ora_reminder"),
}


def enable_immediate_email(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Preference = apps.get_model("notifications", "NotificationPreference")
    database = schema_editor.connection.alias
    preferences = Preference.objects.using(database)
    types = {kind: app for app, kinds in TYPES_BY_APP.items() for kind in kinds}
    last_id = 0
    while True:
        user_ids = list(
            User.objects.using(database).filter(pk__gt=last_id)
            .order_by("pk").values_list("pk", flat=True)[:500]
        )
        if not user_ids:
            break
        existing = set(
            preferences.filter(user_id__in=user_ids, type__in=types)
            .values_list("user_id", "type")
        )
        preferences.bulk_create([
            Preference(
                user_id=user_id, app=app, type=kind,
                web=True, push=False, email=True, email_cadence="Immediately",
            )
            for user_id in user_ids
            for kind, app in types.items()
            if (user_id, kind) not in existing
        ], batch_size=500, ignore_conflicts=True)
        # Includes rows inserted concurrently by upstream's registration handler.
        # Preserve existing web/push choices.
        preferences.filter(user_id__in=user_ids, type__in=types).update(
            email=True, email_cadence="Immediately",
        )
        last_id = user_ids[-1]


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("notifications", "0012_digestschedule"),
    ]
    operations = [
        migrations.RunPython(enable_immediate_email, migrations.RunPython.noop),
    ]
