"""
Tests for Course Teams configuration.
"""
from __future__ import absolute_import, unicode_literals

import ddt
import six
from django.test import TestCase

from ..teams_config import TeamsConfig, TeamsetConfig


@ddt.ddt
class TeamsConfigTests(TestCase):
    """
    Test cases for `TeamsConfig` functions.
    """
    @ddt.data(
        None,
        "not-a-dict",
        {},
        {"max_team_size": 5},
        {"team_sets": []},
        {"team_sets": "not-a-list"},
        {"team_sets": ["not-a-dict"]},
        {"topics": None, "random_key": 88},
    )
    def test_disabled_team_configs(self, data):
        """
        Test that configuration that doesn't specify any valid team-sets
        is considered disabled.
        """
        teams_config = TeamsConfig(data)
        assert not teams_config.is_enabled

    INPUT_DATA_1 = {
        "max_team_size": 5,
        "topics": [
            {
                "id": "bananas",
                "max_team_size": 10,
                "type": "private_managed",
            },
            {
                "id": "bokonism",
                "name": "BOKONISM",
                "description": "Busy busy busy",
                "type": "open",
                "max_team_size": 2,
            },
            {
                # Clusters with duplicate IDs should be dropped.
                "id": "bananas",
                "name": "All about Bananas",
                "description": "Not to be confused with bandanas",
            },

        ],
    }

    OUTPUT_DATA_1 = {
        "max_team_size": 5,
        "team_sets": [
            {
                "id": "bananas",
                "name": "bananas",
                "description": "",
                "max_team_size": 10,
                "type": "private_managed",
            },
            {
                "id": "bokonism",
                "name": "BOKONISM",
                "description": "Busy busy busy",
                "max_team_size": 2,
                "type": "open",
            },
        ]
    }

    INPUT_DATA_2 = {
        "team_sets": [
            {
                # Team-set should be dropped due to lack of ID.
                "name": "Assignment about existence",
            },
            {
                # Team-set should be dropped due to invalid ID.
                "id": ["not", "a", "string"],
                "name": "Assignment about strings",
            },
            {
                # Team-set should be dropped due to invalid ID.
                "id": "Not a slug.",
                "name": "Assignment about slugs",
            },
            {
                # All fields invalid except ID;
                # Team-set will exist but have all fallbacks.
                "id": "horses",
                "name": {"assignment", "about", "horses"},
                "description": object(),
                "max_team_size": -1000,
                "type": "matrix",
                "extra_key": "Should be ignored",
            },
            [
                # Team-set should be dropped because it's not a dict.
                "this", "isn't", "a", "valid", "team-set"
            ],
        ],
    }

    OUTPUT_DATA_2 = {
        "max_team_size": None,
        "team_sets": [
            {
                "id": "horses",
                "name": "horses",
                "description": "",
                "max_team_size": None,
                "type": "open",
            },
        ],
    }

    @ddt.data(
        (INPUT_DATA_1, OUTPUT_DATA_1),
        (INPUT_DATA_2, OUTPUT_DATA_2),
    )
    @ddt.unpack
    def test_teams_config_round_trip(self, input_data, expected_output_data):
        """
        Test that when we load some config data,
        it is cleaned in the way we expect it to be.
        """
        teams_config = TeamsConfig(input_data)
        actual_output_data = teams_config.cleaned_data
        self.assertDictEqual(actual_output_data, expected_output_data)

    @ddt.data(
        (None, None, "open", None),
        (None, None, "public_managed", None),
        (None, 6666, "open", 6666),
        (None, 6666, "public_managed", None),
        (1812, None, "open", 1812),
        (1812, None, "public_managed", None),
        (1812, 6666, "open", 6666),
        (1812, 6666, "public_managed", None),
    )
    @ddt.unpack
    def test_calc_max_team_size(
            self,
            course_run_max_team_size,
            teamset_max_team_size,
            teamset_type,
            expected_max_team_size,
    ):
        """
        Test that a team set's max team size is calculated as expected.
        """
        teamset_data = {"id": "teamset-1", "name": "Team size testing team-set"}
        teamset_data["max_team_size"] = teamset_max_team_size
        teamset_data["type"] = teamset_type
        config_data = {
            "max_team_size": course_run_max_team_size,
            "team_sets": [teamset_data],
        }
        config = TeamsConfig(config_data)
        assert config.calc_max_team_size("teamset-1") == expected_max_team_size

    def test_teams_config_string(self):
        """
        Assert that teams configs can be reasonably stringified.
        """
        config = TeamsConfig({})
        assert six.text_type(config) == "Teams configuration for 0 team-sets"

    def test_teamset_config_string(self):
        """
        Assert that team-set configs can be reasonably stringified.
        """
        config = TeamsetConfig({"id": "omlette-du-fromage"})
        assert six.text_type(config) == "omlette-du-fromage"

    def test_teams_config_repr(self):
        """
        Assert that the developer-friendly repr isn't broken.
        """
        config = TeamsConfig({"team_sets": [{"id": "hedgehogs"}], "max_team_size": 987})
        config_repr = repr(config)
        assert isinstance(config_repr, six.string_types)

        # When repr() fails, it doesn't always throw an exception.
        # Instead, it puts error messages in the repr.
        assert 'Error' not in config_repr

        # Instead of checking the specific string,
        # just make sure important info is there.
        assert 'TeamsetConfig' in config_repr
        assert 'TeamsConfig' in config_repr
        assert '987' in config_repr
        assert 'open' in config_repr
        assert 'hedgehogs' in config_repr
