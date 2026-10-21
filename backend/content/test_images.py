import base64
from io import BytesIO, StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID, uuid4

from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from access.services import replace_grant
from content.images import MAX_IMAGE_BYTES
from content.models import ContentImage
from core.domain import DomainError, mutation
from core.models import MutationLock
from remarks.services import change_remark
from remarks.tests import RemarkFixtures
from tasks.services import change_task, preview_task


def image_upload(fmt='PNG', raw=None):
    if raw is None:
        output = BytesIO()
        Image.new('RGB', (8, 6), color='green').save(output, format=fmt)
        raw = output.getvalue()
    return {'id': str(uuid4()), 'data': base64.b64encode(raw).decode()}


class ImageTests(RemarkFixtures, TransactionTestCase):
    def setUp(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_remarks()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = override_settings(MEDIA_ROOT=self.directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def files(self):
        return list(Path(self.directory.name).glob('images/*'))

    def edit(self, uploads, text=None):
        self.task.refresh_from_db()
        return change_task(self.alice, 'edit', {'description': text if text is not None else '\n'.join(f"[image:{i['id']}]" for i in uploads),
                                              'images': uploads, 'expected_revision': self.task.revision}, self.task.pk)

    def test_verified_formats_private_download_and_live_containment_permissions(self):
        for fmt in ('PNG', 'JPEG', 'WEBP'):
            item = image_upload(fmt)
            self.edit([item])
            image = ContentImage.objects.get(pk=item['id'])
            self.assertEqual((image.format, image.width, image.height), (fmt, 8, 6))
            path = f'/api/v1/images/{image.pk}/'
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(b''.join(response.streaming_content), base64.b64decode(item['data']))
            response.close()
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.client.force_authenticate(self.bob)
        self.compound(self.alice, 'move', {'parent': None, 'project': str(self.other.pk)}, self.task)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {'task_write': True})
        self.assertEqual(self.client.get(path).status_code, 404)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {'task_read': True})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        response.close()
        (Path(self.directory.name) / image.file_name).unlink()
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_size_boundary_invalid_content_animation_and_pixel_limit_are_atomic(self):
        raw = base64.b64decode(image_upload()['data'])
        exact = image_upload(raw=raw + b'\0' * (MAX_IMAGE_BYTES - len(raw)))
        self.edit([exact])
        self.assertEqual(ContentImage.objects.get(pk=exact['id']).size, MAX_IMAGE_BYTES)
        before = MutationLock.objects.get(pk='domain').revision
        output = BytesIO()
        Image.new('RGB', (5000, 4001)).save(output, format='PNG')
        animated = BytesIO()
        Image.new('RGB', (2, 2), 'red').save(animated, format='WEBP', save_all=True,
                                           append_images=[Image.new('RGB', (2, 2), 'blue')], duration=100, loop=0)
        for data in (b'', b'<svg/>', raw[:30], raw + b'\0' * (MAX_IMAGE_BYTES + 1 - len(raw)),
                     output.getvalue(), animated.getvalue()):
            item = image_upload(raw=data)
            with self.subTest(size=len(data)):
                response = self.client.patch(f'/api/v1/tasks/{self.task.pk}/', {
                    'description': f"[image:{item['id']}]", 'images': [item], 'expected_revision': 1}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(ContentImage.objects.count(), 1)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, before)
        for uploads in ([image_upload()] * 6, [{'id': str(uuid4()), 'data': '@@@'}],
                        [{'id': str(uuid4()), 'data': exact['data'], 'owner': 'forged'}]):
            response = self.client.patch(f'/api/v1/tasks/{self.task.pk}/', {
                'description': '\n'.join(f"[image:{i['id']}]" for i in uploads),
                'images': uploads, 'expected_revision': 1}, format='json')
            self.assertEqual(response.status_code, 400, response.data)

    def test_failed_database_or_partial_file_writes_remove_new_files_and_keep_old_ones(self):
        old = image_upload()
        self.edit([old])
        original = self.files()
        stale = image_upload()
        with self.assertRaises(DomainError) as error:
            change_task(self.alice, 'edit', {'description': f"[image:{stale['id']}]", 'images': [stale], 'expected_revision': 0}, self.task.pk)
        self.assertEqual(error.exception.code, 'stale_revision')
        self.assertEqual(self.files(), original)
        for failure in ('database', 'file'):
            item = image_upload()
            original_save = FileSystemStorage.save
            def failed_save(storage, *args, **kwargs):
                original_save(storage, *args, **kwargs)
                raise OSError('Synthetic write failure')
            target = patch.object(MutationLock, 'save', side_effect=OSError('Synthetic commit failure')) if failure == 'database' else patch.object(FileSystemStorage, 'save', failed_save)
            with target, self.assertRaises(OSError):
                self.edit([item])
            self.assertEqual(self.files(), original)
            self.assertEqual(list(ContentImage.objects.values_list('pk', flat=True)), [UUID(old['id'])])
            self.task.refresh_from_db()
            self.assertIn(old['id'], self.task.description)
            self.assertEqual(self.task.revision, 1)
        @mutation
        def failed_parent():
            self.edit([image_upload()])
            raise OSError('Synthetic enclosing mutation failure')
        with self.assertRaises(OSError):
            failed_parent()
        self.assertEqual(self.files(), original)
        self.assertEqual(ContentImage.objects.count(), 1)

    def test_cleanup_failure_keeps_committed_upload_and_can_be_pruned(self):
        self.edit([image_upload()])
        old = self.files()[0]
        with patch.object(FileSystemStorage, 'delete', side_effect=OSError('Synthetic cleanup failure')), self.assertLogs(level='ERROR'):
            self.edit([image_upload()])
        self.assertEqual(ContentImage.objects.count(), 1)
        new = ContentImage.objects.get()
        self.assertTrue((Path(self.directory.name) / new.file_name).exists())
        self.assertTrue(old.exists())
        os.utime(old, (1, 1))
        call_command('prune_content_images', stdout=StringIO())
        self.assertFalse(old.exists())

    def test_remark_images_write_only_access_source_deletion_and_task_preview(self):
        item = image_upload()
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk,
                      {'task_read': True, 'task_write': True, 'remark_write': True})
        result = change_remark(self.alice, 'create', {'body': f"[image:{item['id']}]", 'images': [item]}, self.task.pk)
        self.assertEqual(set(result), {'id', 'revision'})
        path = f"/api/v1/images/{item['id']}/"
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_authenticate(self.bob)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        response.close()
        preview = preview_task(self.alice, 'delete', {'expected_revision': 0}, self.task.pk)
        self.assertEqual(preview['delete']['images'], 1)
        self.assertNotIn(item['data'], str(preview))
        with transaction.atomic():
            self.compound(self.alice, 'delete', {}, self.task)
        self.assertFalse(self.files())
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_token_removal_cleans_only_after_commit_and_ids_cannot_be_reassigned(self):
        item = image_upload()
        self.edit([item])
        with self.assertRaises(DomainError):
            change_remark(self.alice, 'create', {'body': f"[image:{item['id']}]", 'images': [item]}, self.task.pk)
        with self.assertRaises(DomainError):
            self.edit([image_upload()], text='No token')
        with transaction.atomic():
            self.edit([], text='Removed image')
            self.assertTrue(self.files())
            self.assertFalse(ContentImage.objects.exists())
        self.assertFalse(self.files())

    def test_orphan_pruning_preserves_recent_and_referenced_files_and_reports_missing(self):
        self.edit([image_upload()])
        old = Path(self.directory.name) / 'images' / 'orphan.png'
        old.write_bytes(b'orphan')
        os.utime(old, (1, 1))
        recent = old.with_name('recent.png')
        recent.write_bytes(b'recent')
        output = StringIO()
        call_command('prune_content_images', stdout=output)
        self.assertIn('Removed 1 orphan files; 0 referenced files missing', output.getvalue())
        self.assertTrue(recent.exists())
        self.assertEqual(len(self.files()), 2)
