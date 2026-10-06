"""Run in the LMS test environment to verify API and metadata compatibility."""
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from common.djangoapps.student.models import PendingNameChange
from common.djangoapps.student.models_api import confirm_name_change, do_name_change_request
from common.djangoapps.student.tests.factories import UserFactory
from common.djangoapps.student.views.management import do_email_change_request
from openedx.core.djangoapps.user_api.accounts.api import update_account_settings
from openedx.core.djangoapps.user_api.accounts.serializers import get_extended_profile
from openedx.core.djangoapps.user_api.errors import AccountValidationError


@override_settings(ACCOUNT_READ_ONLY_FIELDS=('name', 'email'))
class AccountFieldPolicyIntegrationTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def test_identity_patch_is_rejected_before_other_changes(self):
        for field, value in [('name', 'New Name'), ('email', 'new@example.com')]:
            with self.subTest(field=field), self.assertRaises(AccountValidationError):
                update_account_settings(self.user, {field: value, 'bio': 'Must not save'})
        self.user.profile.refresh_from_db()
        self.assertNotEqual(self.user.profile.bio, 'Must not save')

    def test_legacy_name_and_email_requests_are_blocked(self):
        with self.assertRaises(PermissionDenied):
            do_name_change_request(self.user, 'New Name', 'test')
        with self.assertRaises(PermissionDenied):
            do_email_change_request(self.user, 'new@example.com')
        pending = PendingNameChange.objects.create(user=self.user, new_name='Old Request', rationale='test')
        with self.assertRaises(PermissionDenied):
            confirm_name_change(self.user, pending)

    def test_metadata_is_preserved_and_other_fields_remain_available(self):
        profile = self.user.profile
        profile.set_meta({'company': 'Historical Company', 'work_experience': '10'})
        profile.save()
        update_account_settings(self.user, {'bio': 'New biography'})
        profile.refresh_from_db()
        with patch(
            'openedx.core.djangoapps.user_api.accounts.serializers.configuration_helpers.get_value',
            return_value=['work_experience'],
        ):
            self.assertEqual(get_extended_profile(profile), [
                {'field_name': 'work_experience', 'field_value': '10'},
            ])
        self.assertEqual(profile.get_meta()['company'], 'Historical Company')
        self.assertEqual(profile.bio, 'New biography')
