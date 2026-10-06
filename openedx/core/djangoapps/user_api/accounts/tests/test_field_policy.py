"""Site-level account field policy tests."""
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings

from openedx.core.djangoapps.user_api.accounts.field_policy import require_editable_account_field


@override_settings(ACCOUNT_READ_ONLY_FIELDS=('name', 'email'))
class AccountFieldPolicyTests(SimpleTestCase):
    def test_identity_fields_are_locked(self):
        for field in ('name', 'email'):
            with self.subTest(field=field), self.assertRaises(PermissionDenied):
                require_editable_account_field(field)

    def test_other_fields_remain_editable(self):
        require_editable_account_field('bio')
        require_editable_account_field('country')

    @override_settings(ACCOUNT_READ_ONLY_FIELDS=())
    def test_policy_disabled(self):
        require_editable_account_field('name')
        require_editable_account_field('email')
