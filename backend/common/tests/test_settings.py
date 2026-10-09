"""Garde-fous sur les réglages sensibles."""
from django.conf import settings
from django.test import SimpleTestCase

import config.settings as config_settings


class ThrottleRatesTests(SimpleTestCase):
    """Les limites anti-abus restent celles de la production par défaut."""

    def test_production_rates_are_unchanged_without_factor(self):
        rates = config_settings._throttle_rates({"service_request": "10/hour", "auth_login": "10/minute"}, debug=False)
        self.assertEqual(rates, {"service_request": "10/hour", "auth_login": "10/minute"})

    def test_factor_multiplies_the_count_and_keeps_the_period(self):
        import os

        os.environ["KEMTA_THROTTLE_FACTOR"] = "30"
        try:
            rates = config_settings._throttle_rates({"service_request": "10/hour"}, debug=True)
        finally:
            os.environ.pop("KEMTA_THROTTLE_FACTOR")
        self.assertEqual(rates, {"service_request": "300/hour"})

    def test_factor_is_ignored_outside_development(self):
        import os

        os.environ["KEMTA_THROTTLE_FACTOR"] = "30"
        try:
            rates = config_settings._throttle_rates({"service_request": "10/hour"}, debug=False)
        finally:
            os.environ.pop("KEMTA_THROTTLE_FACTOR")
        self.assertEqual(rates, {"service_request": "10/hour"})

    def test_invalid_factor_falls_back_to_the_production_rate(self):
        import os

        os.environ["KEMTA_THROTTLE_FACTOR"] = "beaucoup"
        try:
            rates = config_settings._throttle_rates({"anon": "90/minute"}, debug=True)
        finally:
            os.environ.pop("KEMTA_THROTTLE_FACTOR")
        self.assertEqual(rates, {"anon": "90/minute"})

    def test_effective_settings_keep_a_bounded_public_limit(self):
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        for scope in ("service_request", "auth_login", "otp", "auth_register"):
            self.assertRegex(rates[scope], r"^\d+/(minute|hour|day)$")
