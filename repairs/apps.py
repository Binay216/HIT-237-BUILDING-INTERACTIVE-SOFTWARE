from django.apps import AppConfig


class RepairsConfig(AppConfig):
    name = 'repairs'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import repairs.signals  # noqa: F401
