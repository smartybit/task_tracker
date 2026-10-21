import base64
import binascii
from io import BytesIO
import re
import warnings
from uuid import UUID, uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from content.models import ContentImage
from core.api import StrictSerializer
from core.domain import DomainError, on_mutation_rollback
from tasks.models import Task

MAX_IMAGE_BYTES = 2_097_152
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_TOKEN = re.compile(r'\[image:([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\]')
FORMATS = {'PNG': ('png', 'image/png'), 'JPEG': ('jpg', 'image/jpeg'), 'WEBP': ('webp', 'image/webp')}


def image_storage():
    return FileSystemStorage(location=settings.MEDIA_ROOT)


class ImageInput(StrictSerializer):
    id = serializers.UUIDField()
    data = serializers.CharField(max_length=((MAX_IMAGE_BYTES + 2) // 3) * 4, trim_whitespace=False)

    def validate(self, values):
        try:
            raw = base64.b64decode(values['data'], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise serializers.ValidationError('Enter a base64-encoded image.') from exc
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise serializers.ValidationError('Each image must be at most 2 MiB (2,097,152 bytes).')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw), formats=list(FORMATS)) as image:
                    if image.width * image.height > MAX_IMAGE_PIXELS or getattr(image, 'n_frames', 1) != 1:
                        raise ValueError('Oversized or animated image')
                    fmt, width, height = image.format, image.width, image.height
                    image.verify()
                with Image.open(BytesIO(raw), formats=list(FORMATS)) as image:
                    image.load()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as exc:
            raise serializers.ValidationError('Use a valid static PNG, JPEG, or WebP image, up to 20 million pixels.') from exc
        return {**values, 'data': raw, 'format': fmt, 'width': width, 'height': height}


def image_upload_field():
    return ImageInput(many=True, max_length=5, required=False, default=list)


def validate_image_tokens(text, uploads):
    targets = {UUID(pk) for pk in IMAGE_TOKEN.findall(text)}
    ids = [item['id'] for item in uploads]
    if len(set(ids)) != len(ids) or not set(ids) <= targets:
        raise DomainError('invalid_input', 'Each new image needs one unique ID present in its containing text.')
    if ContentImage.objects.filter(pk__in=ids).exists():
        raise DomainError('conflict', 'An image ID is already in use. Insert the image again with a new ID.', 409)


def sync_images(source, uploads):
    field, text = ('source_task', source.description) if isinstance(source, Task) else ('source_remark', source.body)
    validate_image_tokens(text, uploads)
    desired = {UUID(pk) for pk in IMAGE_TOKEN.findall(text)}
    storage = image_storage()
    for item in uploads:
        name = f"images/{uuid4().hex}.{FORMATS[item['format']][0]}"
        # Register before writing so partial writes are cleaned too. Names are
        # generated internally; a failed write never overwrites an existing file.
        on_mutation_rollback(lambda name=name: storage.delete(name))
        stored = storage.save(name, ContentFile(item['data']))
        if stored != name:
            on_mutation_rollback(lambda name=stored: storage.delete(name))
        ContentImage.objects.create(id=item['id'], **{field: source}, file_name=stored,
                                    format=item['format'], size=len(item['data']),
                                    width=item['width'], height=item['height'])
    ContentImage.objects.filter(**{field: source}).exclude(pk__in=desired).delete()
