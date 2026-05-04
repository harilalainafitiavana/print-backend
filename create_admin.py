import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projet.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

email = os.getenv("ADMIN_EMAIL")
password = os.getenv("ADMIN_PASSWORD")

if email and password:
    if not User.objects.filter(email=email).exists():
        print("Création de l'admin...")

        User.objects.create_superuser(
            email=email,
            password=password
        )
    else:
        print("Admin déjà existant")
else:
    print("Variables ADMIN_EMAIL ou ADMIN_PASSWORD manquantes")