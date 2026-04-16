"""
Django app configuration for fraud detection.
"""

from django.apps import AppConfig


class FraudDetectionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fraud_detection'
    verbose_name = 'Fraud Detection'
