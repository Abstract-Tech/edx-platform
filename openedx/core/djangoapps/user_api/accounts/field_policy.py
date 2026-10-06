"""Site-level restrictions on learner-editable account fields."""

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _


def require_editable_account_field(field):
    """Also protect legacy change requests and previously issued confirmation links."""
    if field in getattr(settings, 'ACCOUNT_READ_ONLY_FIELDS', ()):
        raise PermissionDenied(_("This account field is managed by your organization."))
