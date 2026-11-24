"""Isolated Limes regressions (Django 5.2, no services or outgoing email).

Run: python limes_notification_policy/tests/regression.py
Service boundaries are mocked; the migration executor uses a minimal upstream
schema fixture. Run the LMS integration suite against MySQL before release too.
"""

import ast
from contextlib import nullcontext
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT
SOURCE = ROOT
NOTIFICATIONS = Path("openedx/core/djangoapps/notifications")
sys.path.insert(0, str(ROOT))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_function(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
    )
    node.decorator_list = []
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace
    )
    return namespace[name]


class SourceFixTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT

    def test_new_registration_uses_immediate_defaults(self):
        settings_code = (
            (ROOT / "lms/envs/common.py")
            .read_text()
            .split("# Limes defaults; persisted user choices still take precedence.")[1]
        )
        config = {"INSTALLED_APPS": []}
        exec(settings_code, config)
        self.assertEqual(config["NOTIFICATION_IMMEDIATE_EMAIL_BUFFER_MINUTES"], 0)
        self.assertNotIn("NOTIFICATION_CREATION_BATCH_SIZE", config)
        policy = load_module(
            "migration_policy",
            ASSETS
            / "limes_notification_policy/migrations/0001_immediate_email_defaults.py",
        )
        defaults = {
            kind: {
                **config["NOTIFICATION_TYPES_OVERRIDE"][kind],
                "push": False,
                "notification_app": app,
            }
            for app, kinds in policy.TYPES_BY_APP.items()
            for kind in kinds
        }
        self.assertEqual(len(defaults), 14)
        factory = load_function(
            SOURCE / NOTIFICATIONS / "models.py",
            "create_notification_preference",
            {
                "NotificationPreference": SimpleNamespace,
                "get_default_values_of_preferences": lambda: defaults,
            },
        )
        manager = Mock()
        register = load_function(
            SOURCE / NOTIFICATIONS / "handlers.py",
            "create_user_account_preferences",
            {
                "transaction": SimpleNamespace(atomic=nullcontext),
                "COURSE_NOTIFICATION_TYPES": defaults,
                "create_notification_preference": factory,
                "NotificationPreference": SimpleNamespace(objects=manager),
                "IntegrityError": Exception,
                "ProgrammingError": Exception,
                "log": Mock(),
            },
        )
        register(None, SimpleNamespace(id=1001), True)
        created = manager.bulk_create.call_args.args[0]
        self.assertEqual(len(created), 14)
        self.assertTrue(
            all(p.email and p.email_cadence == "Immediately" for p in created)
        )
        manager.reset_mock()
        register(None, SimpleNamespace(id=1001), False)
        manager.bulk_create.assert_not_called()

    def test_discussion_grouping_disabled_but_staff_grouping_preserved(self):
        path = self.root / NOTIFICATIONS / "grouping_notifications.py"
        tree = ast.parse(path.read_text())
        tree.body = [
            n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))
        ]
        from abc import ABC, abstractmethod
        from typing import Dict, Type, Union

        namespace = dict(
            ABC=ABC,
            abstractmethod=abstractmethod,
            Dict=Dict,
            Type=Type,
            Union=Union,
            Notification=object,
            COURSE_NOTIFICATION_TYPES=[
                "new_discussion_post",
                "new_response",
                "response_on_followed_post",
                "ora_staff_notifications",
            ],
        )
        exec(compile(tree, str(path), "exec"), namespace)
        registry = namespace["NotificationRegistry"]
        for kind in [
            "new_discussion_post",
            "new_response",
            "response_on_followed_post",
        ]:
            self.assertIsNone(registry.get_grouper(kind))
        self.assertIsNotNone(registry.get_grouper("ora_staff_notifications"))
        self.assertNotIn(
            "'uuid': new_notification.content_context.get('uuid')", path.read_text()
        )

    def test_zero_buffer_sends_each_event_without_consulting_prior_mail(self):
        user = SimpleNamespace(username="learner")
        notification_model = Mock()
        namespace = dict(
            User=object, Notification=notification_model, get_buffer_minutes=lambda: 0
        )
        decide = load_function(
            self.root / NOTIFICATIONS / "email/tasks.py",
            "decide_email_action",
            namespace,
        )
        for _ in range(3):
            self.assertEqual(decide(user, "course", object()), "send_immediate")
        notification_model.objects.select_for_update.assert_not_called()

    def test_all_batches_reach_email_sender_and_opt_out_is_respected(self):
        rows = []

        class Notification:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.content = "notification"

        class Notifications:
            def bulk_create(self, batch):
                rows.extend(batch)

            def filter(self, **kwargs):
                return [
                    r
                    for r in rows
                    if r.user_id in kwargs["user_id__in"]
                    and r.content_context["uuid"] == kwargs["content_context__uuid"]
                ]

        Notification.objects = Notifications()

        def preference(user_id):
            return SimpleNamespace(
                user_id=user_id,
                is_enabled_for_any_channel=lambda *args: True,
                get_channels_for_notification_type=lambda *args: (
                    ["web"] if user_id == 1 else ["web", "email"]
                ),
                get_email_cadence_for_notification_type=lambda *args: "Immediately",
            )

        preference_manager = SimpleNamespace(
            filter=lambda **kwargs: [preference(i) for i in kwargs["user_id__in"]]
        )
        send_email = Mock()
        filtered_out = set()
        namespace = dict(
            uuid=SimpleNamespace(uuid4=lambda: "unique-event"),
            DISABLE_NOTIFICATIONS=SimpleNamespace(is_enabled=lambda: False),
            CourseKey=SimpleNamespace(from_string=lambda key: key),
            is_notification_valid=lambda *args: True,
            settings=SimpleNamespace(NOTIFICATION_CREATION_BATCH_SIZE=76),
            NotificationRegistry=SimpleNamespace(get_grouper=lambda kind: None),
            get_default_values_of_preferences=lambda: {},
            ENABLE_PUSH_NOTIFICATIONS=SimpleNamespace(is_enabled=lambda key: False),
            get_list_in_batches=lambda values, size: [
                values[i : i + size] for i in range(0, len(values), size)
            ],
            logger=Mock(),
            NotificationFilter=lambda: SimpleNamespace(
                apply_filters=lambda ids, *args: [
                    i for i in ids if i not in filtered_out
                ]
            ),
            NotificationPreference=SimpleNamespace(objects=preference_manager),
            Notification=Notification,
            EmailCadence=SimpleNamespace(
                IMMEDIATELY="Immediately", DAILY="Daily", WEEKLY="Weekly"
            ),
            send_immediate_cadence_email=send_email,
            notification_generated_event=Mock(),
            send_ace_msg_to_push_channel=Mock(),
        )
        send = load_function(
            self.root / NOTIFICATIONS / "tasks.py", "send_notifications", namespace
        )
        # Empty, exact boundary, partial final batch, duplicate recipients, large audience.
        for count in [0, 1, 2, 75, 76, 77, 152, 153, 2050]:
            for kind in [
                "new_discussion_post",
                "new_question_post",
                "new_response",
                "response_on_followed_post",
                "new_comment",
                "new_comment_on_response",
                "comment_on_followed_post",
                "new_instructor_all_learners_post",
            ]:
                with self.subTest(count=count, kind=kind):
                    rows.clear()
                    send_email.reset_mock()
                    filtered_out.clear()
                    filtered_out.add(3)
                    ids = list(range(1, count + 1))
                    send(
                        ids + ids,
                        "course",
                        "discussion",
                        kind,
                        {
                            "email_content": "fresh content",
                            "group_by_id": "same-thread",
                        },
                        "/post",
                    )
                    self.assertEqual(len(rows), len(set(ids) - filtered_out))
                    expected = set(ids) - filtered_out - {1}
                    if kind in ["new_discussion_post", "new_question_post"]:
                        expected = set()
                        self.assertTrue(all(not r.email for r in rows))
                    if expected:
                        self.assertEqual(set(send_email.call_args.args[0]), expected)
                        self.assertEqual(send_email.call_count, 1)
                        self.assertTrue(
                            all(
                                r.content_context["email_content"] == "fresh content"
                                for r in send_email.call_args.args[0].values()
                            )
                        )
                    else:
                        send_email.assert_not_called()

    def test_regular_posts_never_email_for_any_cadence(self):
        rows = []

        class Notification:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.content = "notification"

        class Notifications:
            def bulk_create(self, batch):
                rows.extend(batch)

            def filter(self, **kwargs):
                return [
                    r
                    for r in rows
                    if r.user_id in kwargs["user_id__in"]
                    and r.content_context["uuid"] == kwargs["content_context__uuid"]
                ]

        Notification.objects = Notifications()

        def preference(user_id):
            return SimpleNamespace(
                user_id=user_id,
                is_enabled_for_any_channel=lambda *args: True,
                get_channels_for_notification_type=lambda *args: (
                    ["web"] if user_id == 1 else ["web", "email"]
                ),
                get_email_cadence_for_notification_type=lambda *args: cadence,
            )

        preference_manager = SimpleNamespace(
            filter=lambda **kwargs: [preference(i) for i in kwargs["user_id__in"]]
        )
        send_email = Mock()
        filtered_out = set()
        namespace = dict(
            uuid=SimpleNamespace(uuid4=lambda: "unique-event"),
            DISABLE_NOTIFICATIONS=SimpleNamespace(is_enabled=lambda: False),
            CourseKey=SimpleNamespace(from_string=lambda key: key),
            is_notification_valid=lambda *args: True,
            settings=SimpleNamespace(NOTIFICATION_CREATION_BATCH_SIZE=76),
            NotificationRegistry=SimpleNamespace(get_grouper=lambda kind: None),
            get_default_values_of_preferences=lambda: {},
            ENABLE_PUSH_NOTIFICATIONS=SimpleNamespace(is_enabled=lambda key: False),
            get_list_in_batches=lambda values, size: [
                values[i : i + size] for i in range(0, len(values), size)
            ],
            logger=Mock(),
            NotificationFilter=lambda: SimpleNamespace(
                apply_filters=lambda ids, *args: [
                    i for i in ids if i not in filtered_out
                ]
            ),
            NotificationPreference=SimpleNamespace(objects=preference_manager),
            Notification=Notification,
            EmailCadence=SimpleNamespace(
                IMMEDIATELY="Immediately", DAILY="Daily", WEEKLY="Weekly"
            ),
            send_immediate_cadence_email=send_email,
            notification_generated_event=Mock(),
            send_ace_msg_to_push_channel=Mock(),
        )
        send = load_function(
            self.root / NOTIFICATIONS / "tasks.py", "send_notifications", namespace
        )
        scheduler = Mock()
        namespace["schedule_bulk_digest_emails"] = scheduler
        for cadence in ["Immediately", "Daily", "Weekly"]:
            for kind in [
                "new_discussion_post",
                "new_question_post",
                "new_instructor_all_learners_post",
            ]:
                with self.subTest(cadence=cadence, kind=kind):
                    rows.clear()
                    send_email.reset_mock()
                    scheduler.reset_mock()
                    send([1, 2, 3, 4, 5], "course", "discussion", kind, {}, "/post")
                    if kind != "new_instructor_all_learners_post":
                        self.assertTrue(all(not row.email for row in rows))
                        send_email.assert_not_called()
                        scheduler.assert_not_called()
                    elif cadence == "Immediately":
                        self.assertEqual(
                            set(send_email.call_args.args[0]), {2, 3, 4, 5}
                        )
                        scheduler.assert_not_called()
                    else:
                        send_email.assert_not_called()
                        self.assertEqual(
                            scheduler.call_args.args[0],
                            {i: cadence for i in [2, 3, 4, 5]},
                        )

    def test_followers_beyond_first_page_with_incorrect_metadata(self):
        tree = ast.parse(
            (
                ROOT / "lms/djangoapps/discussion/rest_api/discussions_notifications.py"
            ).read_text()
        )
        cls = next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "DiscussionNotificationSender"
        )
        method = next(
            n
            for n in cls.body
            if isinstance(n, ast.FunctionDef)
            and n.name == "send_response_on_followed_post_notification"
        )
        for count in (0, 1, 20, 21, 40, 41, 182):
            with self.subTest(count=count):
                ids = list(range(1, count + 1))

                def fetch(thread, course, query_params):
                    page = query_params["page"]
                    return SimpleNamespace(
                        num_pages=1,
                        collection=[
                            {"subscriber_id": i}
                            for i in ids[(page - 1) * 20 : page * 20]
                        ],
                    )

                namespace = {
                    "Subscription": SimpleNamespace(fetch=Mock(side_effect=fetch)),
                    "clean_thread_html_body": lambda s: s,
                }
                exec(
                    compile(
                        ast.Module(body=[method], type_ignores=[]), "sender", "exec"
                    ),
                    namespace,
                )
                sender = Mock(
                    thread=SimpleNamespace(id="thread"),
                    course=SimpleNamespace(id="course"),
                    parent_id=None,
                    comment=SimpleNamespace(body="reply"),
                )
                sender._check_if_subscriber_is_not_thread_or_content_creator.side_effect = (
                    lambda i: i != 1
                )
                namespace[method.name](sender)
                self.assertEqual(
                    set(sender._send_notification.call_args.args[0]), set(ids) - {1}
                )
                self.assertEqual(
                    namespace["Subscription"].fetch.call_count, (count + 19) // 20 + 1
                )

    def test_broadcast_task_does_not_also_send_follower_notifications(self):
        import sys
        from unittest.mock import patch

        path = ROOT / "lms/djangoapps/discussion/rest_api/tasks.py"
        for broadcast in (True, False):
            sender = Mock()
            namespace = {
                "CourseKey": SimpleNamespace(from_string=lambda x: x),
                "DISABLE_NOTIFICATIONS": SimpleNamespace(is_enabled=lambda: False),
                "Thread": Mock(),
                "User": Mock(),
                "get_course_with_access": Mock(),
                "DiscussionNotificationSender": Mock(return_value=sender),
            }
            with patch.dict(
                sys.modules,
                {
                    "limes_notification_policy.policy": SimpleNamespace(
                        broadcast_reply=Mock(return_value=broadcast)
                    )
                },
            ):
                send = load_function(path, "send_response_notifications", namespace)
                send("thread", "course", 1, "comment")
            self.assertEqual(
                sender.send_response_on_followed_post_notification.call_count,
                0 if broadcast else 1,
            )


# Use the real Django ORM and migration executor against an isolated SQLite DB.
# The fixture supplies only the upstream schema needed by the data migration.
_fixture = tempfile.TemporaryDirectory()
fixture_root = Path(_fixture.name)
app = fixture_root / "fixture_notifications"
(app / "migrations").mkdir(parents=True)
(app / "__init__.py").write_text("")
(app / "migrations/__init__.py").write_text("")
(app / "apps.py").write_text("""from django.apps import AppConfig
class NotificationsConfig(AppConfig):
    name = 'fixture_notifications'
    label = 'notifications'
""")
(app / "migrations/0012_digestschedule.py").write_text(
    """from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='NotificationPreference', fields=[
        ('id', models.AutoField(primary_key=True)),
        ('user', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE)),
        ('app', models.CharField(max_length=128)), ('type', models.CharField(max_length=128)),
        ('web', models.BooleanField(default=True)), ('push', models.BooleanField(default=False)),
        ('email', models.BooleanField(default=False)), ('email_cadence', models.CharField(max_length=64)),
        ('is_active', models.BooleanField(default=True)),
    ], options={'unique_together': {('user', 'app', 'type')}}),
    migrations.CreateModel(name='Notification', fields=[
        ('id', models.AutoField(primary_key=True)),
        ('course_id', models.CharField(max_length=255)),
        ('notification_type', models.CharField(max_length=100)),
        ('content_context', models.JSONField(default=dict)),
        ('content_url', models.CharField(max_length=500)),
    ])]
"""
)
sys.path[:0] = [str(fixture_root), str(ASSETS)]
from django.conf import settings

settings.configure(
    SECRET_KEY="test-only",
    USE_TZ=True,
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "fixture_notifications.apps.NotificationsConfig",
        "limes_notification_policy",
    ],
)
import django

django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class RolloutMigrationTests(unittest.TestCase):
    def test_existing_missing_and_future_preferences(self):
        before = [
            ("notifications", "0012_digestschedule"),
            ("auth", "0012_alter_user_first_name_max_length"),
        ]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        User = apps.get_model("auth", "User")
        Preference = apps.get_model("notifications", "NotificationPreference")
        User.objects.bulk_create([User(username=f"learner-{i}") for i in range(502)])
        user = User.objects.order_by("pk").first()
        pref = Preference.objects.create(
            user_id=user.pk,
            app="discussion",
            type="new_discussion_post",
            web=False,
            push=True,
            email=False,
            email_cadence="Weekly",
        )
        staff = Preference.objects.create(
            user_id=user.pk,
            app="grading",
            type="ora_staff_notifications",
            email=False,
            email_cadence="Daily",
        )
        target = [("limes_notification_policy", "0001_immediate_email_defaults")]
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        pref.refresh_from_db()
        self.assertTrue(pref.email)
        self.assertEqual(pref.email_cadence, "Immediately")
        self.assertFalse(pref.web)
        self.assertTrue(pref.push)
        self.assertEqual(
            Preference.objects.filter(email=True, email_cadence="Immediately").count(),
            502 * 14,
        )
        staff.refresh_from_db()
        self.assertFalse(staff.email)
        # A later user choice must not be reset by a repeat deployment/migration.
        pref.email = False
        pref.email_cadence = "Weekly"
        pref.save()
        count = Preference.objects.count()
        executor = MigrationExecutor(connection)
        self.assertEqual(executor.migration_plan(target), [])
        executor.migrate(target)
        pref.refresh_from_db()
        self.assertFalse(pref.email)
        self.assertEqual(pref.email_cadence, "Weekly")
        self.assertEqual(Preference.objects.count(), count)

        # Upgrade from the old plugin's recorded 0001 to the fork's 0002.
        Notification = apps.get_model("notifications", "Notification")
        for course, kind, context, url in [
            (
                "A",
                "new_instructor_all_learners_post",
                {"thread_id": "checked"},
                "/posts/checked",
            ),
            (
                "A",
                "new_instructor_all_learners_post",
                {"thread_id": "checked"},
                "/posts/checked",
            ),
            ("B", "new_instructor_all_learners_post", {}, "/posts/historical?x=1"),
            (
                "A",
                "new_discussion_post",
                {"thread_id": "unchecked"},
                "/posts/unchecked",
            ),
        ]:
            Notification.objects.create(
                course_id=course,
                notification_type=kind,
                content_context=context,
                content_url=url,
            )
        target = [("limes_notification_policy", "0002_broadcastthread")]
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(target)
        self.assertEqual([(m.app_label, m.name) for m, backwards in plan], target)
        executor.migrate(target)
        pref.refresh_from_db()
        self.assertFalse(pref.email)
        self.assertEqual(pref.email_cadence, "Weekly")
        BroadcastThread = executor.loader.project_state(target).apps.get_model(
            "limes_notification_policy", "BroadcastThread"
        )
        self.assertEqual(
            set(BroadcastThread.objects.values_list("course_id", "thread_id")),
            {("A", "checked"), ("B", "historical")},
        )
        executor = MigrationExecutor(connection)
        self.assertEqual(executor.migration_plan(target), [])
        executor.migrate(target)
        self.assertEqual(BroadcastThread.objects.count(), 2)
        # Compare the historical model state with the current app model.
        from django.db.migrations.state import ModelState
        from limes_notification_policy.models import BroadcastThread as Current

        old_state = ModelState.from_model(BroadcastThread)
        new_state = ModelState.from_model(Current)
        self.assertEqual(old_state, new_state)


policy_ast = ast.parse((ROOT / "limes_notification_policy/policy.py").read_text())


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.manager = Mock()
        self.manager.filter.return_value.exists.return_value = True
        self.ns = {
            "BroadcastThread": SimpleNamespace(objects=self.manager),
            "get_user_role_names": Mock(return_value={"Moderator"}),
            "CourseStaffRole": Mock(),
            "CourseInstructorRole": Mock(),
            "can_user_notify_all_learners": Mock(return_value=True),
            "clean_thread_html_body": lambda s: s,
            "FORUM_ROLE_ADMINISTRATOR": "Administrator",
            "FORUM_ROLE_MODERATOR": "Moderator",
            "FORUM_ROLE_COMMUNITY_TA": "Community TA",
        }
        for node in policy_ast.body:
            if isinstance(node, ast.FunctionDef):
                exec(
                    compile(ast.Module(body=[node], type_ignores=[]), "policy", "exec"),
                    self.ns,
                )
        self.sender = Mock(
            course=SimpleNamespace(id="course-A"),
            thread=SimpleNamespace(id="thread-A"),
            parent_id=None,
            comment=SimpleNamespace(body="new reply"),
            comment_id="reply-1",
        )
        self.sender._create_cohort_course_audience.return_value = {}

    def test_checked_authorized_persisted(self):
        self.ns["remember_broadcast_thread"](
            self.sender.thread, "course-A", object(), True
        )
        self.manager.get_or_create.assert_called_once_with(
            course_id="course-A", thread_id="thread-A"
        )

    def test_unchecked_not_persisted(self):
        self.ns["remember_broadcast_thread"](
            self.sender.thread, "course-A", object(), False
        )
        self.manager.get_or_create.assert_not_called()

    def test_unauthorized_checked_not_persisted(self):
        self.ns["can_user_notify_all_learners"].return_value = False
        self.ns["remember_broadcast_thread"](
            self.sender.thread, "course-A", object(), True
        )
        self.manager.get_or_create.assert_not_called()

    def test_reply_broadcast(self):
        self.assertTrue(self.ns["broadcast_reply"](self.sender))
        self.sender._send_course_wide_notification.assert_called_once_with(
            "response_on_followed_post",
            {},
            {"email_content": "new reply", "group_by_id": "reply-1"},
        )
        self.manager.filter.assert_called_once_with(
            course_id="course-A", thread_id="thread-A"
        )

    def test_unchecked_uses_original_audience(self):
        self.manager.filter.return_value.exists.return_value = False
        self.assertFalse(self.ns["broadcast_reply"](self.sender))
        self.sender._send_course_wide_notification.assert_not_called()

    def test_nested_comment(self):
        self.sender.parent_id = "response-1"
        self.sender.parent_response = SimpleNamespace(username="alice")
        self.assertTrue(self.ns["broadcast_reply"](self.sender))
        args = self.sender._send_course_wide_notification.call_args.args
        self.assertEqual(args[0], "comment_on_followed_post")
        self.assertEqual(args[2]["author_name"], "alice's")

    def test_cohort_restrictions_preserved(self):
        self.sender._create_cohort_course_audience.return_value = {"cohorts": [7]}
        self.ns["broadcast_reply"](self.sender)
        self.assertEqual(
            self.sender._send_course_wide_notification.call_args.args[1],
            {
                "cohorts": [7],
                "course_roles": ["staff", "instructor"],
                "discussion_roles": ["Administrator", "Moderator", "Community TA"],
            },
        )


if __name__ == "__main__":
    unittest.main()
