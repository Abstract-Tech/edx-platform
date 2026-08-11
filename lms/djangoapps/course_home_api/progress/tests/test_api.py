"""
Tests for the Python APIs exposed by the Progress API of the Course Home API app.
"""

from unittest.mock import patch

from django.test import TestCase

from lms.djangoapps.course_home_api.progress.api import (
    _subsection_has_attempt,
    calculate_progress_for_learner_in_course,
    aggregate_assignment_type_grade_summary,
)
from opaque_keys.edx.locator import BlockUsageLocator, CourseLocator
from xmodule.graders import ShowCorrectness
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


def _make_subsection(
    fmt,
    earned,
    possible,
    show_corr,
    *,
    due_delta_days=None,
    attempted: bool = True,
    learner_attempted: bool | None = None,
    problem_scores=None,
):
    """Build a lightweight subsection object for testing aggregation scenarios."""
    graded_total = SimpleNamespace(earned=earned, possible=possible)
    due = None
    if due_delta_days is not None:
        due = datetime.now(timezone.utc) + timedelta(days=due_delta_days)
    if learner_attempted is None:
        learner_attempted = attempted
    return SimpleNamespace(
        graded=True,
        format=fmt,
        graded_total=graded_total,
        all_total=SimpleNamespace(first_attempted=None),
        show_correctness=show_corr,
        due=due,
        show_grades=lambda staff: True,
        attempted_graded=attempted,
        attempted=learner_attempted,
        problem_scores=problem_scores or {},
    )


_AGGREGATION_SCENARIOS = [
    (
        'all_visible_always',
        {'type': 'Homework', 'weight': 1.0, 'drop_count': 0, 'min_count': 2, 'short_label': 'HW'},
        [
            _make_subsection('Homework', 1, 1, ShowCorrectness.ALWAYS),
            _make_subsection('Homework', 0.5, 1, ShowCorrectness.ALWAYS),
        ],
        {'avg': 0.75, 'weighted': 0.75, 'hidden': 'none', 'pending': 'none', 'final': 0.75},
    ),
    (
        'some_hidden_never_but_include',
        {'type': 'Exam', 'weight': 1.0, 'drop_count': 0, 'min_count': 2, 'short_label': 'EX'},
        [
            _make_subsection('Exam', 1, 1, ShowCorrectness.ALWAYS),
            _make_subsection('Exam', 0.5, 1, ShowCorrectness.NEVER_BUT_INCLUDE_GRADE),
        ],
        {'avg': 0.5, 'weighted': 0.5, 'hidden': 'some', 'pending': 'none', 'final': 0.75},
    ),
    (
        'all_hidden_never_but_include',
        {'type': 'Quiz', 'weight': 1.0, 'drop_count': 0, 'min_count': 2, 'short_label': 'QZ'},
        [
            _make_subsection('Quiz', 0.4, 1, ShowCorrectness.NEVER_BUT_INCLUDE_GRADE),
            _make_subsection('Quiz', 0.6, 1, ShowCorrectness.NEVER_BUT_INCLUDE_GRADE),
        ],
        {'avg': 0.0, 'weighted': 0.0, 'hidden': 'all', 'pending': 'none', 'final': 0.5},
    ),
    (
        'past_due_mixed_visibility',
        {'type': 'Lab', 'weight': 1.0, 'drop_count': 0, 'min_count': 2, 'short_label': 'LB'},
        [
            _make_subsection('Lab', 0.8, 1, ShowCorrectness.PAST_DUE, due_delta_days=-1),
            _make_subsection('Lab', 0.2, 1, ShowCorrectness.PAST_DUE, due_delta_days=+3),
        ],
        {'avg': 0.4, 'weighted': 0.4, 'hidden': 'some', 'pending': 'none', 'final': 0.5},
    ),
    (
        'drop_lowest_keeps_high_scores',
        {'type': 'Project', 'weight': 1.0, 'drop_count': 2, 'min_count': 4, 'short_label': 'PR'},
        [
            _make_subsection('Project', 1, 1, ShowCorrectness.ALWAYS),
            _make_subsection('Project', 1, 1, ShowCorrectness.ALWAYS),
            _make_subsection('Project', 0, 1, ShowCorrectness.ALWAYS),
            _make_subsection('Project', 0, 1, ShowCorrectness.ALWAYS),
        ],
        {'avg': 1.0, 'weighted': 1.0, 'hidden': 'none', 'pending': 'none', 'final': 1.0},
    ),
    (
        'some_pending_not_yet_graded',
        {'type': 'ORA', 'weight': 1.0, 'drop_count': 0, 'min_count': 2, 'short_label': 'ORA'},
        [
            _make_subsection('ORA', 1, 1, ShowCorrectness.ALWAYS, attempted=True),
            _make_subsection('ORA', 0, 1, ShowCorrectness.ALWAYS, attempted=False, learner_attempted=True),
        ],
        {'avg': 0.5, 'weighted': 0.5, 'hidden': 'none', 'pending': 'some', 'final': 0.5},
    ),
    (
        'all_pending_not_yet_graded',
        {'type': 'Staff Graded', 'weight': 1.0, 'drop_count': 0, 'min_count': 1, 'short_label': 'SG'},
        [
            _make_subsection('Staff Graded', 0, 1, ShowCorrectness.ALWAYS, attempted=False, learner_attempted=True),
        ],
        {'avg': 0.0, 'weighted': 0.0, 'hidden': 'none', 'pending': 'all', 'final': 0.0},
    ),
]


class ProgressApiTests(TestCase):
    """
    Tests for the progress calculation functions.
    """

    @patch("lms.djangoapps.course_home_api.progress.api.get_course_blocks_completion_summary")
    def test_calculate_progress_for_learner_in_course(self, mock_get_summary):
        """
        A test to verify functionality of the function under test.
        """
        mock_get_summary.return_value = {
            "complete_count": 5,
            "incomplete_count": 2,
            "locked_count": 1,
        }

        expected_data = {
            "complete_count": 5,
            "incomplete_count": 2,
            "locked_count": 1,
            "total_count": 8,
            "complete_percentage": 0.62,
            "locked_percentage": 0.12,
            "incomplete_percentage": 0.26,
        }

        results = calculate_progress_for_learner_in_course("some_course", "some_user")
        assert mock_get_summary.called_once_with("some_course", "some_user")
        assert results == expected_data

    @patch("lms.djangoapps.course_home_api.progress.api.get_course_blocks_completion_summary")
    def test_handle_division_by_zero(self, mock_get_summary):
        """
        A test to verify that we're avoiding division-by-zero errors if the total number of units is 0.
        """
        mock_get_summary.return_value = {
            "complete_count": 0,
            "incomplete_count": 0,
            "locked_count": 0,
        }

        expected_data = {
            "complete_count": 0,
            "incomplete_count": 0,
            "locked_count": 0,
            "total_count": 0,
            "complete_percentage": 0.0,
            "locked_percentage": 0.0,
            "incomplete_percentage": 0.0,
        }

        results = calculate_progress_for_learner_in_course("some_course", "some_user")
        assert mock_get_summary.called_once_with("some_course", "some_user")
        assert results == expected_data

    @patch("lms.djangoapps.course_home_api.progress.api.get_course_blocks_completion_summary")
    def test_calculate_progress_for_learner_in_course_summary_empty(self, mock_get_summary):
        """
        A test to verify functionality of the function under test if a block summary is not received.
        """
        mock_get_summary.return_value = {}

        results = calculate_progress_for_learner_in_course("some_course", "some_user")
        assert not results

    def test_aggregate_assignment_type_grade_summary_scenarios(self):
        """
        A test to verify functionality of aggregate_assignment_type_grade_summary.
            1. Test visibility modes (always, never but include grade, past due)
            2. Test drop-lowest behavior
            3. Test weighting behavior
            4. Test final grade calculation
            5. Test average grade calculation
            6. Test weighted grade calculation
            7. Test has_hidden_contribution calculation
        """

        for case_name, policy, subsections, expected in _AGGREGATION_SCENARIOS:
            with self.subTest(case_name=case_name):
                course_grade = SimpleNamespace(chapter_grades={'chapter': {'sections': subsections}})
                grading_policy = {'GRADER': [policy]}

                result = aggregate_assignment_type_grade_summary(
                    course_grade,
                    grading_policy,
                    has_staff_access=False,
                )

                assert 'results' in result and 'final_grades' in result
                assert result['final_grades'] == expected['final']
                assert len(result['results']) == 1

                row = result['results'][0]
                assert row['type'] == policy['type'], case_name
                assert row['average_grade'] == expected['avg']
                assert row['weighted_grade'] == expected['weighted']
                assert row['has_hidden_contribution'] == expected['hidden']
                assert row['has_pending_grades'] == expected['pending']
                assert row['num_droppable'] == policy['drop_count']

    def test_aggregate_assignment_type_grade_summary_ignores_unscored_subsections_for_pending(self):
        course_grade = SimpleNamespace(chapter_grades={
            'chapter': {
                'sections': [
                    _make_subsection('Homework', 0, 0, ShowCorrectness.ALWAYS, attempted=False),
                ],
            },
        })
        grading_policy = {'GRADER': [{
            'type': 'Homework',
            'weight': 1.0,
            'drop_count': 0,
            'min_count': 1,
            'short_label': 'HW',
        }]}

        result = aggregate_assignment_type_grade_summary(
            course_grade,
            grading_policy,
            has_staff_access=False,
        )

        assert result['results'] == []

    @patch('lms.djangoapps.course_home_api.progress.api.Submission')
    @patch('lms.djangoapps.course_home_api.progress.api.anonymous_id_for_user')
    def test_subsection_has_attempt_detects_ora_submission_via_anonymous_user(self, mock_anonymous_id, mock_submission):
        course_key = CourseLocator.from_string('course-v1:test+test+yt')
        ora_key = BlockUsageLocator.from_string(
            'block-v1:test+test+yt+type@openassessment+block@f23c7540101e4887a08d4e903f449305'
        )
        subsection = SimpleNamespace(
            all_total=SimpleNamespace(first_attempted=None),
            attempted=False,
            problem_scores={ora_key: SimpleNamespace(first_attempted=None)},
        )
        user = SimpleNamespace()
        mock_anonymous_id.side_effect = ['course-anon-id', 'global-anon-id']
        mock_submission.objects.filter.return_value.exists.return_value = True

        assert _subsection_has_attempt(subsection, user=user, course_key=course_key) is True

        mock_submission.objects.filter.assert_called_once_with(
            student_item__student_id__in=['course-anon-id', 'global-anon-id'],
            student_item__course_id=str(course_key),
            student_item__item_id=str(ora_key),
            student_item__item_type='openassessment',
        )

    @patch('lms.djangoapps.course_home_api.progress.api.Submission')
    @patch('lms.djangoapps.course_home_api.progress.api.anonymous_id_for_user')
    def test_aggregate_assignment_type_grade_summary_marks_anonymous_ora_submission_as_pending(
        self, mock_anonymous_id, mock_submission,
    ):
        course_key = CourseLocator.from_string('course-v1:test+test+yt')
        ora_key = BlockUsageLocator.from_string(
            'block-v1:test+test+yt+type@openassessment+block@f23c7540101e4887a08d4e903f449305'
        )
        subsection = _make_subsection(
            'ORA',
            0,
            1,
            ShowCorrectness.ALWAYS,
            attempted=False,
            learner_attempted=False,
            problem_scores={ora_key: SimpleNamespace(first_attempted=None)},
        )
        course_grade = SimpleNamespace(
            user=SimpleNamespace(),
            course_data=SimpleNamespace(course=SimpleNamespace(id=course_key)),
            chapter_grades={'chapter': {'sections': [subsection]}},
        )
        grading_policy = {'GRADER': [{
            'type': 'ORA',
            'weight': 1.0,
            'drop_count': 0,
            'min_count': 1,
            'short_label': 'ORA',
        }]}
        mock_anonymous_id.side_effect = ['course-anon-id', 'global-anon-id']
        mock_submission.objects.filter.return_value.exists.return_value = True

        result = aggregate_assignment_type_grade_summary(
            course_grade,
            grading_policy,
            has_staff_access=False,
        )

        assert result['results'][0]['has_pending_grades'] == 'all'
