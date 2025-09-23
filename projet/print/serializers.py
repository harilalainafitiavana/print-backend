from rest_framework import serializers
from .models import Produits, Utilisateurs

#ModelSerializer Sert à transformer les informations dans la table produits en forme JSON pour que react peux le récupérer
class ProduitsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produits
        fields = '__all__'

class UtilisateursSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateurs
        fields = ['nom', 'prenom', 'email', 'num_tel', 'mdp', 'role', 'profils']
        extra_kwargs = {'mdp': {'write_only': True}}

    def create(self, validated_data):
        from django.contrib.auth.hashers import make_password
        validated_data['mdp'] = make_password(validated_data['mdp'])
        return super().create(validated_data)


# Recevoir et envoyé la réponse au react pour afficher la liste des utilisteur
class UsersList(serializers.ModelSerializer):
    class Meta:
        model = Utilisateurs
        fields = ['id', 'nom', 'prenom', 'email', 'num_tel', 'role', 'profils', 'date_inscription']