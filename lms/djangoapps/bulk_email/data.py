"""
Bulk Email Data

This provides Data models to represent Bulk Email data.
"""


class BulkEmailTargetChoices:
    """
    Enum for the available targets (recipient groups) of an email authored with the bulk course email tool.

    SEND_TO_MYSELF      - Message intended for author of the message
    SEND_TO_STAFF       - Message intended for all course staff
    SEND_TO_LEARNERS    - Message intended for all enrolled learners
    SEND_TO_COHORT      - Message intended for a specific cohort
    SEND_TO_TRACK       - Message intended for all learners in a specific track (e.g. audit or verified)
    """
    SEND_TO_MYSELF = "myself"
    SEND_TO_STAFF = "staff"
    SEND_TO_LEARNERS = "learners"
    SEND_TO_COHORT = "cohort"
    SEND_TO_TRACK = "track"
    # Optional: expose the four score buckets (these are *exact* values).
    SEND_TO_SCORE_0 = "score[0]"
    SEND_TO_SCORE_1_39 = "score[1-39]"
    SEND_TO_SCORE_40_69 = "score[40-69]"
    SEND_TO_SCORE_70_100 = "score[70-100]"

    TARGET_CHOICES = (SEND_TO_MYSELF, SEND_TO_STAFF, SEND_TO_LEARNERS, SEND_TO_COHORT, SEND_TO_TRACK, # optional:
        SEND_TO_SCORE_0,
        SEND_TO_SCORE_1_39,
        SEND_TO_SCORE_40_69,
        SEND_TO_SCORE_70_100,)


    @classmethod
    def is_valid_target(cls, target):
        """
        Given the target of a message, return a boolean indicating whether the target choice is valid.
        """
        return target in cls.TARGET_CHOICES
