from django.db import models


class MutationLock(models.Model):
    key = models.CharField(max_length=20, primary_key=True)
    revision = models.PositiveBigIntegerField(default=0)
