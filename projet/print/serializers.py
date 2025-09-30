from rest_framework import serializers
from .models import Produits, Utilisateurs, Commande, ConfigurationImpression, Fichier, Paiement
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


# Sérializers de base pour la récupération de tout les commande
class BaseConfigurationImpressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationImpression
        fields = '__all__'   # version complète par défaut


class BaseFichierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fichier
        fields = [
            'id', 'nom_fichier', 'fichier', 'format', 'taille',
            'resolution_dpi', 'profil_couleur', 'date_upload'
        ]


# Côté User (simplifié) pour la gestion des commandes
class ConfigurationImpressionUserSerializer(BaseConfigurationImpressionSerializer):
    class Meta(BaseConfigurationImpressionSerializer.Meta):
        fields = '__all__'


class CommandeSerializer(serializers.ModelSerializer):
    configuration = ConfigurationImpressionUserSerializer()
    fichiers = BaseFichierSerializer(many=True, read_only=True)
    phone = serializers.SerializerMethodField()
    montant_total = serializers.SerializerMethodField()

    class Meta:
        model = Commande
        fields = [
            'id', 'date_commande', 'statut', 'mode_paiement',
            'configuration', 'fichiers', 'phone', 'montant_total'
        ]

    def get_phone(self, obj):
        return getattr(obj.paiement, 'phone', None)

    def get_montant_total(self, obj):
        return obj.calculer_montant() if obj.configuration else 0



# Côté Admin (plus détaillé) pour la gestion des commandes
class ConfigurationImpressionAdminSerializer(BaseConfigurationImpressionSerializer):
    class Meta(BaseConfigurationImpressionSerializer.Meta):
        fields = [
            'id', 'format_type', 'small_format', 'largeur', 'hauteur',
            'paper_type', 'finish', 'quantity', 'duplex', 'binding',
            'cover_paper', 'options'
        ]


class PaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ['id', 'phone', 'montant', 'transaction_id', 'statut_paiement']


class CommandeAdminSerializer(serializers.ModelSerializer):
    configuration = ConfigurationImpressionAdminSerializer()
    fichiers = BaseFichierSerializer(many=True, read_only=True)
    paiement = PaiementSerializer(read_only=True)
    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    montant_total = serializers.SerializerMethodField()

    class Meta:
        model = Commande
        fields = [
            'id', 'date_commande', 'statut', 'mode_paiement',
            'configuration', 'fichiers', 'paiement',
            'user_email', 'user_name', 'user_phone', 'montant_total'
        ]

    def get_user_email(self, obj):
        return getattr(obj.utilisateur, 'email', None)

    def get_user_name(self, obj):
        if obj.utilisateur:
            return f"{getattr(obj.utilisateur, 'prenom', '')} {getattr(obj.utilisateur, 'nom', '')}"
        return None

    def get_user_phone(self, obj):
        return getattr(obj.paiement, 'phone', None)

    def get_montant_total(self, obj):
        try:
            return obj.calculer_montant() if obj.configuration else 0
        except:
            return 0



# Modifier le profil utilisateur
class ProfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateurs
        fields = ['nom', 'prenom', 'email', 'num_tel', 'profils']
        read_only_fields = ['id', 'email'] # L'user n'est pas autorisé de modifier son email

    # ✅ Ajouter update pour gérer FormData et fichiers
    def update(self, instance, validated_data):
        instance.nom = validated_data.get('nom', instance.nom)
        instance.prenom = validated_data.get('prenom', instance.prenom)
        instance.email = validated_data.get('email', instance.email)
        instance.num_tel = validated_data.get('num_tel', instance.num_tel)

        # ⚠️ Gestion du fichier
        profils = validated_data.get('profils', None)
        if profils:
            instance.profils = profils

        instance.save()
        return instance



# Envoyer des notifications
class NotificationSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    message = serializers.CharField(max_length=500)
