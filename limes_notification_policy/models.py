from django.db import models


class BroadcastThread(models.Model):
    course_id = models.CharField(max_length=255)
    thread_id = models.CharField(max_length=255)

    class Meta:
        unique_together = (("course_id", "thread_id"),)
