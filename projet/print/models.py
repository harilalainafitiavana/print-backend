from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from decimal import Decimal



class Produits(models.Model):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=355)
    categorie = models.CharField(max_length=155)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='Imageproduit/', null=True, blank=True)
    future = models.CharField(max_length=155, null=True, blank=True)

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
    role = models.CharField(max_length=20, default='USER')  # USER ou ADMIN
    date_inscription = models.DateTimeField(auto_now_add=True)
    profils = models.ImageField(upload_to='Profiluser/', null=True, blank=True)

    # Champs obligatoires pour AbstractBaseUser
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Accès admin
    # is_superuser vient de PermissionsMixin

    objects = UtilisateurManager()

    USERNAME_FIELD = 'email'  # login avec email
    REQUIRED_FIELDS = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.role})"



# -----------------------------
# Configuration d'impression
# -----------------------------
class ConfigurationImpression(models.Model):
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
    ]
    binding = models.CharField(max_length=20, choices=BINDING_CHOICES, null=True, blank=True)

    COVER_CHOICES = [
        ('simple', 'Papier simple'),
        ('photo', 'Papier photo'),
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
    utilisateur = models.ForeignKey("Utilisateurs", on_delete=models.CASCADE)
    configuration = models.OneToOneField(ConfigurationImpression, on_delete=models.CASCADE)
    date_commande = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=100, default="en_attente")
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    mode_paiement = models.CharField(max_length=155)
    
    is_deleted = models.BooleanField(default=False) 

    def __str__(self):
        return f"Commande {self.id} - {self.utilisateur}"

    def calculer_montant(self):
        """Calcule le montant total selon la configuration impression"""
        config = self.configuration

        # ⚠️ Tu peux modifier ces prix sans migration
        prix_par_m2 = Decimal("5000.00")
        prix_formats = {
            "A3": Decimal("1000.00"),
            "A4": Decimal("500.00"),
            "A5": Decimal("300.00"),
            "A6": Decimal("200.00"),
        }

        if config.format_type == "grand":
            surface = (config.largeur / 100) * (config.hauteur / 100)  # cm → m
            if surface < 1:
                surface = Decimal("1.00")  # min 1 m²
            montant = surface * prix_par_m2 * config.quantity
        elif config.format_type == "petit":
            if config.small_format == "custom":
                surface = (config.largeur / 100) * (config.hauteur / 100)
                montant = surface * prix_par_m2 * config.quantity
            else:
                montant = prix_formats.get(config.small_format, Decimal("0")) * config.quantity
        else:
            montant = Decimal("0")

        return montant

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

