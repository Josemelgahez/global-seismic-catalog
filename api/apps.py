from django.apps import AppConfig
from django.db.models.signals import post_migrate

def create_default_metadata(sender, **kwargs):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "admin")
        print("[✓] Default admin created after migrations")

class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        post_migrate.connect(create_default_metadata, sender=self)
