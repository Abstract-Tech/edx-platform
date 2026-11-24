"""Keep the app label and table names used by the former Tutor plugin."""

from django.apps import AppConfig


class LimesNotificationPolicyConfig(AppConfig):
    name = "limes_notification_policy"
    default_auto_field = "django.db.models.BigAutoField"
