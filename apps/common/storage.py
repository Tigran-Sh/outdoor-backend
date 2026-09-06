"""Storage for files that must never be served directly.

``MEDIA_ROOT`` is public: the web server maps it to ``MEDIA_URL`` with no
authentication, so anything written there is readable by anyone holding
(or guessing) the URL. Identity documents cannot live there.

Files stored here land outside that tree and are only reachable through
a view that checks permissions first.
"""

import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMediaStorage(FileSystemStorage):
    """Filesystem storage rooted outside the public media tree."""

    # Read as plain properties rather than the cached ones the base class
    # uses, so overriding the setting (tests, per-environment config)
    # takes effect.
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        # Refusing to build a URL means a serializer can never
        # accidentally leak a direct link to one of these files.
        raise ValueError("Private media has no public URL.")


private_media_storage = PrivateMediaStorage()
