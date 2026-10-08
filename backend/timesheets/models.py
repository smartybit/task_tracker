from django.conf import settings
from django.db import models


class Timesheet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.PROTECT)
    revision = models.PositiveBigIntegerField(default=0)
