from rest_framework import serializers
from .models import Produits, Utilisateurs
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

#ModelSerializer Sert à transformer les informations dans la table produits en forme JSON pour que react peux le récupérer
class ProduitsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produits
        fields = '__all__'


# Insérer l'utilsateur dans la base de donnée après avoir fait l'inscription
class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateurs
        # "confirm_password" doit être dans fields
        fields = ['nom', 'prenom', 'email', 'num_tel', 'password', 'confirm_password', 'profils']

    def validate_email(self, value):
        if Utilisateurs.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email déjà utilisé")
        return value

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas"})

        # Vérifie la force du mot de passe
        try:
            validate_password(password)
        except ValidationError as e:
            raise serializers.ValidationError({"password": e.messages})

        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)  # Supprime confirm_password
        password = validated_data.pop('password')
        user = Utilisateurs(**validated_data)
        user.set_password(password)
        user.save()
        return user



# Recevoir et envoyé la réponse au react pour afficher la liste des utilisteur
class UsersList(serializers.ModelSerializer):
    class Meta:
        model = Utilisateurs
        fields = ['id', 'nom', 'prenom', 'email', 'num_tel', 'role', 'profils', 'date_inscription']



# Login de connexion
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    
    username_field = "email"  # SimpleJWT saura utiliser 'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        # Vérifie si l'email existe
        try:
            user = Utilisateurs.objects.get(email=email)
        except Utilisateurs.DoesNotExist:
            raise serializers.ValidationError({"email": "Votre email est incorrect 😓"})

        # Vérifie le mot de passe
        if not user.check_password(password):
            raise serializers.ValidationError({"password": "Vous avez un erreur dans votre mot de passe 😉"})

        # Authentifie pour JWT
        attrs = {"email": email, "password": password}
        data = super().validate(attrs)
        data["role"] = user.role
        return data

