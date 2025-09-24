from django.contrib.auth.backends import BaseBackend
from .models import Utilisateurs
from django.contrib.auth.hashers import check_password


class EmailBackend(BaseBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        # print("Authenticating user with email:", email)
        try:
            user = Utilisateurs.objects.get(email=email)
            if check_password(password, user.password):
                return user
        except Utilisateurs.DoesNotExist:
            print("User does not exist")
            return None

    def get_user(self, user_id):
        try:
            return Utilisateurs.objects.get(pk=user_id)
        except Utilisateurs.DoesNotExist:
            return None
