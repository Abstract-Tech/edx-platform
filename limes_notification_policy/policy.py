from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole
from lms.djangoapps.discussion.django_comment_client.utils import get_user_role_names
from lms.djangoapps.discussion.rest_api.utils import can_user_notify_all_learners
from lms.djangoapps.discussion.rest_api.discussions_notifications import (
    clean_thread_html_body,
)
from openedx.core.djangoapps.django_comment_common.models import (
    FORUM_ROLE_ADMINISTRATOR,
    FORUM_ROLE_MODERATOR,
    FORUM_ROLE_COMMUNITY_TA,
)
from .models import BroadcastThread


def remember_broadcast_thread(thread, course_key, user, checked):
    if checked and can_user_notify_all_learners(
        get_user_role_names(user, course_key),
        CourseStaffRole(course_key).has_user(user),
        CourseInstructorRole(course_key).has_user(user),
    ):
        BroadcastThread.objects.get_or_create(
            course_id=str(course_key), thread_id=str(thread.id)
        )


def broadcast_reply(sender):
    if not BroadcastThread.objects.filter(
        course_id=str(sender.course.id),
        thread_id=str(sender.thread.id),
    ).exists():
        return False
    kind = (
        "comment_on_followed_post" if sender.parent_id else "response_on_followed_post"
    )
    context = {"email_content": clean_thread_html_body(sender.comment.body)}
    if sender.parent_id:
        context["author_name"] = f"{sender.parent_response.username}'s"
    sender._populate_context_with_ids_for_mobile(context, kind)
    audience = sender._create_cohort_course_audience()
    if audience:
        audience["course_roles"] = ["staff", "instructor"]
        audience["discussion_roles"] = [
            FORUM_ROLE_ADMINISTRATOR,
            FORUM_ROLE_MODERATOR,
            FORUM_ROLE_COMMUNITY_TA,
        ]
    # Use the upstream course sender/filter pipeline; it excludes the current
    # author and respects access, account status and notification preferences.
    # A per-comment grouping key prevents replies in this thread being merged.
    context["group_by_id"] = str(sender.comment_id)
    sender._send_course_wide_notification(kind, audience, context)
    return True
