"""
WSGI config for the outdoor_backend project.

It exposes the WSGI callable as a module-level variable named
``application``. Uses ``django-configurations`` to bootstrap settings.
"""

import os

from configurations.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "outdoor_backend.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "LocalConf")

application = get_wsgi_application()
