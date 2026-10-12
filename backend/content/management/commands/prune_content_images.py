import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from content.models import ContentImage
from core.models import MutationLock


class Command(BaseCommand):
    help = 'Remove orphan image files older than an hour; report missing referenced files.'

    @transaction.atomic
    def handle(self, *args, **options):
        MutationLock.objects.select_for_update().get(pk='domain')
        root = Path(settings.MEDIA_ROOT)
        referenced = set(ContentImage.objects.values_list('file_name', flat=True))
        removed = 0
        for path in (root / 'images').glob('*'):
            if path.is_file() and str(path.relative_to(root)) not in referenced and path.stat().st_mtime < time.time() - 3600:
                path.unlink()
                removed += 1
        missing = sum(not (root / name).is_file() for name in referenced)
        self.stdout.write(f'Removed {removed} orphan files; {missing} referenced files missing.')
