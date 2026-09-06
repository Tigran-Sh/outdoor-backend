from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.common.validators import (
    MAX_UPLOAD_SIZE,
    validate_document_upload,
    validate_image_upload,
)


def _file(name, size=1024):
    return SimpleUploadedFile(name, b"x" * size)


class UploadValidatorTests(SimpleTestCase):
    def test_accepts_supported_images(self):
        for name in ("logo.png", "logo.JPG", "photo.jpeg", "cover.webp"):
            validate_image_upload(_file(name))

    def test_rejects_unsupported_image_types(self):
        for name in ("logo.svg", "logo.gif", "logo.pdf", "payload.exe"):
            with self.assertRaises(ValidationError, msg=name):
                validate_image_upload(_file(name))

    def test_rejects_missing_extension(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(_file("logo"))

    def test_rejects_oversized_files(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(_file("logo.png", MAX_UPLOAD_SIZE + 1))

    def test_accepts_files_at_the_limit(self):
        validate_image_upload(_file("logo.png", MAX_UPLOAD_SIZE))

    def test_documents_also_accept_pdf(self):
        validate_document_upload(_file("scan.pdf"))
        validate_document_upload(_file("scan.png"))

    def test_documents_still_reject_other_types(self):
        with self.assertRaises(ValidationError):
            validate_document_upload(_file("scan.docx"))
