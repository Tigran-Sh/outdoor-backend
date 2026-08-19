"""Project test runner.

Many permission/validation tests deliberately assert on 4xx responses.
Django logs each of those as a ``django.request`` WARNING, which floods
the test output and makes the pass/fail summary hard to read. This
runner silences logging while tests run so the results stay legible.
"""

import logging

from django.test.runner import DiscoverRunner


class QuietTestRunner(DiscoverRunner):
    def run_tests(self, *args, **kwargs):
        logging.disable(logging.CRITICAL)
        try:
            return super().run_tests(*args, **kwargs)
        finally:
            logging.disable(logging.NOTSET)
