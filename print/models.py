from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from decimal import Decimal


# AJOUTEZ CES CONSTANTES EN HAUT DE models.py (après les imports)
PRIX_PAGE_LIVRE = {
    "A3": Decimal("1000"),
    "A4": Decimal("500"), 
    "A5": Decimal("300"),
    "A6": Decimal("200"),
    "custom": Decimal("200"),
}

PRIX_RELIURE = {
    "spirale": Decimal("2000"),
    "dos_colle": Decimal("3000"), 
    "agrafé": Decimal("1000"),
    "rigide": Decimal("5000"),
    "cousu": Decimal("4000")
}

PRIX_COUVERTURE = {
    "simple": Decimal("1000"),
    "photo": Decimal("3000"),
    "mat": Decimal("4000"),
    "brillant": Decimal("4500"),
    "texture": Decimal("6000")
}

PRIX_DUPLEX = {
    "recto": Decimal("1.0"),
    "recto_verso": Decimal("1.2"),
}

FRAIS_LIVRAISON = Decimal("5000")


class Produits(models.Model):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=355)
    categorie = models.CharField(max_length=155)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='Imageproduit/', null=True, blank=True)
    future = models.CharField(max_length=155, null=True, blank=True)

    format_defaut = models.CharField(
        max_length=5,
        choices=[
            ("A3", "A3"),
            ("A4", "A4"),
            ("A5", "A5"),
            ("A6", "A6"),
        ],
        default="A4",
    )

    # 🆕 Nouveau champ : est-ce un grand format ?
    is_grand_format = models.BooleanField(default=False)
    def __str__(self):
        return self.name
    

# Manager personnalisé pour ton modèle User
class UtilisateurManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # Hashe automatiquement le mot de passe
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


# Modèle Utilisateurs
class Utilisateurs(AbstractBaseUser, PermissionsMixin):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    num_tel = models.CharField(max_length=10, blank=True, null=True)
    code_postal = models.CharField(max_length=150, blank=True, null=True) 
    ville = models.CharField(max_length=150, default='Antananarivo')        
    pays = models.CharField(max_length=100, default='Madagascar') 
    role = models.CharField(max_length=20, default='USER')  # USER ou ADMIN
    date_inscription = models.DateTimeField(auto_now_add=True)
    profils = models.ImageField(upload_to='Profiluser/', null=True, blank=True)

    # ⭐ NOUVEAU CHAMP - Ajoutez cette ligne
    google_avatar_url = models.URLField(blank=True, null=True)

    # Champs obligatoires pour AbstractBaseUser
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Accès admin
    # is_superuser vient de PermissionsMixin

    objects = UtilisateurManager()

    USERNAME_FIELD = 'email'  # login avec email
    REQUIRED_FIELDS = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.role})"
    
    # ⭐ OPTIONNEL - Méthode utilitaire pour obtenir l'avatar
    def get_avatar_url(self):
        """Retourne l'URL de l'avatar (local ou Google)"""
        if self.profils:
            return self.profils.url
        elif self.google_avatar_url:
            return self.google_avatar_url
        return None



# -----------------------------
# Configuration d'impression
# -----------------------------
class ConfigurationImpression(models.Model):
    produit = models.ForeignKey(
        "Produits",  # référence au modèle Produits
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configurations"
    )
    FORMAT_CHOICES = [
        ('petit', 'Petit format'),
        ('grand', 'Grand format'),
    ]
    format_type = models.CharField(max_length=10, choices=FORMAT_CHOICES)

    SMALL_FORMAT_CHOICES = [
        ('A5', 'A5'),
        ('A4', 'A4'),
        ('A3', 'A3'),
        ('custom', 'Personnalisé'),
    ]
    small_format = models.CharField(max_length=10, choices=SMALL_FORMAT_CHOICES, null=True, blank=True)

    largeur = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    hauteur = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    book_pages = models.PositiveIntegerField(null=True, blank=True)
    is_book = models.BooleanField(default=False)

    PAPIER_CHOICES = [
        ('glace', 'Papier glacé'),
        ('mat', 'Papier mat'),
        ('standard', 'Papier standard'),
        ('brillant', 'Papier brillant'),
    ]
    paper_type = models.CharField(max_length=10, choices=PAPIER_CHOICES, null=True, blank=True)

    FINITION_CHOICES = [
        ('brillant', 'Brillant'),
        ('mate', 'Mate'),
        ('standard', 'Standard'),
        ('vernis', 'Vernis Sélectif'),
        ('dorure', 'Dorure à chaud')
    ]
    finish = models.CharField(max_length=10, choices=FINITION_CHOICES, null=True, blank=True)

    quantity = models.PositiveIntegerField()
    
    options = models.TextField(null=True, blank=True) 

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("La quantité doit être un nombre entier positif.")

    # ✅ Nouveaux champs facultatifs
    DUPLEX_CHOICES = [
        ('recto', 'Recto seul'),
        ('recto_verso', 'Recto/verso'),
    ]
    duplex = models.CharField(max_length=20, choices=DUPLEX_CHOICES, null=True, blank=True)

    BINDING_CHOICES = [
        ('spirale', 'Spirale'),
        ('dos_colle', 'Dos collé'),
        ('agrafé', 'Agrafé'),
        ('rigide', 'Couverture rigide'),
        ("cousu", 'Dos caré Cousu')
    ]
    binding = models.CharField(max_length=20, choices=BINDING_CHOICES, null=True, blank=True)

    COVER_CHOICES = [
        ('simple', 'Papier simple'),
        ('photo', 'Papier photo'),
        ('mat', 'Papier couché Mat'),
        ('brillant', 'Papier couché Brillant'),
        ('texture', 'Papier Création Texturé')
    ]
    cover_paper = models.CharField(max_length=20, choices=COVER_CHOICES, null=True, blank=True)

    # Validation existante
    def clean(self):
        if self.format_type == 'grand':
            if self.largeur is None or self.hauteur is None:
                raise ValidationError("Merci de préciser la largeur et la hauteur pour le grand format.")
            if self.largeur > 160 or self.hauteur > 100:
                raise ValidationError("La limite du grand format est 160x100 cm.")

        if self.format_type == 'petit' and self.small_format:
            if self.small_format == 'A5' and self.quantity < 30:
                raise ValidationError("Quantité minimale pour A5 : 30")
            elif self.small_format == 'A4' and self.quantity < 20:
                raise ValidationError("Quantité minimale pour A4 : 20")
            elif self.small_format == 'A3' and self.quantity < 10:
                raise ValidationError("Quantité minimale pour A3 : 10")
            elif self.small_format == 'custom' and self.quantity < 50:
                raise ValidationError("Quantité minimale pour format personnalisé : 50")

# -----------------------------
# Commande
# -----------------------------
class Commande(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('RECU', 'Commande reçue'),
        ('EN_COURS_IMPRESSION', 'En cours d’impression'),
        ('TERMINE', 'Impression terminée'),
        ('EN_COURS_LIVRAISON', 'En cours de livraison'),
        ('LIVREE', 'Livrée'),
    ]
    utilisateur = models.ForeignKey("Utilisateurs", on_delete=models.CASCADE)
    configuration = models.OneToOneField(ConfigurationImpression, on_delete=models.CASCADE)
    date_commande = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default="EN_ATTENTE")
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    mode_paiement = models.CharField(max_length=155)
    
    is_deleted = models.BooleanField(default=False) 

    def __str__(self):
        return f"Commande {self.id} - {self.utilisateur}"

    def calculer_montant(self):
        try:
            print(f"🔍 Début calculer_montant pour commande {self.id}")
            
            config = self.configuration
            if not config:
                print("❌ Pas de configuration")
                return Decimal("10000")
            
            produit = config.produit
            print(f"🔍 Produit: {produit}")
            print(f"🔍 is_book: {config.is_book}, book_pages: {config.book_pages}")
            
            # ✅ CORRECTION : LES LIVRES N'ONT PAS BESOIN DE PRODUIT
            # SI C'EST UN LIVRE - UTILISER LES PRIX FIXES
            if config.is_book and config.book_pages:
                print(f"📖 Calcul LIVRE - Pages: {config.book_pages}, Format: {config.small_format}")
                
                # 1. Prix des pages
                prix_page_livre = PRIX_PAGE_LIVRE.get(config.small_format, PRIX_PAGE_LIVRE["custom"])
                prix_pages = prix_page_livre * config.book_pages * config.quantity
                
                # 2. Prix couverture
                prix_couverture_base = Decimal("0")
                if config.cover_paper in PRIX_COUVERTURE:
                    prix_couverture_base += PRIX_COUVERTURE[config.cover_paper]
                
                multiplicateur_duplex = PRIX_DUPLEX.get(config.duplex, Decimal("1.0"))
                prix_couverture_base *= multiplicateur_duplex
                prix_couverture_total = prix_couverture_base * config.quantity
                
                # 3. Reliure
                prix_reliure = Decimal("0")
                if config.binding in PRIX_RELIURE:
                    prix_reliure = PRIX_RELIURE[config.binding] * config.quantity
                
                # 4. Calcul final
                montant_total = prix_pages + prix_couverture_total + prix_reliure + FRAIS_LIVRAISON
                
                print(f"💰 MONTANT FINAL LIVRE: {montant_total}")
                return montant_total
            
            # ✅ PRODUITS NORMAUX - BESOIN D'UN PRODUIT
            else:
                # ⭐ CETTE VÉRIFICATION RESTE SEULEMENT POUR LES PRODUITS NORMAUX
                if not produit:
                    print("❌ PRODUIT NORMAL SANS PRODUIT - retourne 10000")
                    return Decimal("10000")
                
                print(f"📄 Calcul PRODUIT - Prix: {produit.prix}, Quantité: {config.quantity}")
                
                prix_base = produit.prix
                
                # Ajustement format
                multiplicateur_format = Decimal("1.0")
                if config.small_format != produit.format_defaut:
                    if config.small_format == "A3":
                        multiplicateur_format = Decimal("1.5")
                    elif config.small_format == "A4":
                        multiplicateur_format = Decimal("1.2")
                    elif config.small_format == "custom":
                        multiplicateur_format = Decimal("1.3")
                
                montant_total = (prix_base * multiplicateur_format * config.quantity) + FRAIS_LIVRAISON
                
                print(f"💰 MONTANT FINAL PRODUIT: {montant_total}")
                return montant_total
                
        except Exception as e:
            print(f"💥 ERREUR dans calculer_montant: {e}")
            return Decimal("10000")

    def save(self, *args, **kwargs):
        self.montant_total = self.calculer_montant()  # recalcul automatique
        super().save(*args, **kwargs)

# -----------------------------
# Fichier
# -----------------------------
def fichier_upload_path(instance, filename):
    return f'fichiers/{instance.commande.id}/{filename}'

class Fichier(models.Model):
    commande = models.ForeignKey("Commande", on_delete=models.CASCADE, related_name="fichiers")
    nom_fichier = models.CharField(max_length=255)
    fichier = models.FileField(upload_to=fichier_upload_path, default='')
    format = models.CharField(max_length=50)
    taille = models.DecimalField(max_digits=10, decimal_places=2)
    resolution_dpi = models.IntegerField()
    profil_couleur = models.CharField(max_length=50)
    date_upload = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.resolution_dpi not in [150, 300]:
            raise ValidationError("La résolution doit être 150dpi ou 300dpi.")

        if self.profil_couleur.upper() not in ["CMJN", "CMYK"]:
            raise ValidationError("Le profil couleur doit être CMJN ou CMYK.")

        valid_extensions = ['.pdf', '.jpg', '.jpeg']
        if not any(self.fichier.name.lower().endswith(ext) for ext in valid_extensions):
            raise ValidationError("Le fichier doit être au format .pdf ou .jpeg")

    def __str__(self):
        return self.nom_fichier

# -----------------------------
# Paiement (MVola)
# -----------------------------
class Paiement(models.Model):
    commande = models.OneToOneField(Commande, on_delete=models.CASCADE, related_name="paiement")
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)  # ID MVola
    phone = models.CharField(max_length=20)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    statut_paiement = models.CharField(max_length=50, default="en_attente")  
    date_paiement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Paiement {self.transaction_id or self.id} - {self.statut_paiement}"


class Chat(models.Model):
    utilisateur = models.ForeignKey("Utilisateurs", on_delete=models.CASCADE)
    message = models.TextField()
    type_message = models.CharField(
        max_length=50,
        choices=[('utilisateur', 'Utilisateur'), ('assistant', 'Assistant')]
    )
    date_message = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type_message} - {self.utilisateur} : {self.message[:30]}"


class Contenir(models.Model):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE)
    fichier = models.ForeignKey(Fichier, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("commande", "fichier")


class Communiquer(models.Model):
    utilisateur = models.ForeignKey(Utilisateurs, on_delete=models.CASCADE)
    message = models.ForeignKey(Chat, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("utilisateur", "message")


class Notification(models.Model):
    sender = models.ForeignKey(Utilisateurs, on_delete=models.CASCADE, related_name="sent_notifications", null=True, blank=True)
    user = models.ForeignKey(Utilisateurs, on_delete=models.CASCADE, related_name="notifications")
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        sender_name = f"{self.sender.nom} {self.sender.prenom}" if self.sender else "Admin"
        user_name = f"{self.user.nom} {self.user.prenom}" if self.user else "Utilisateur inconnu"
        return f"Notification de {sender_name} à {user_name}"