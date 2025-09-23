from django.db import models
from django.core.exceptions import ValidationError



class Produits(models.Model):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=355)
    categorie = models.CharField(max_length=155)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='Imageproduit/', null=True, blank=True)
    future = models.CharField(max_length=155, null=True, blank=True)

    def __str__(self):
        return self.name
    

class Utilisateurs(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=255)
    email = models.EmailField(max_length=150, unique=True)
    num_tel = models.CharField(max_length=10)
    mdp = models.CharField(max_length=255)
    role = models.CharField(max_length=20, default='USER')  # USER par défaut
    date_inscription = models.DateTimeField(auto_now_add=True)
    profils = models.ImageField(upload_to='Profiluser/', null=True, blank=True)
    produit = models.ForeignKey("Produits", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.role})"


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
    ]
    paper_type = models.CharField(max_length=10, choices=PAPIER_CHOICES)
    
    FINITION_CHOICES = [
        ('brillant', 'Brillant'),
        ('mate', 'Mate'),
        ('standard', 'Standard'),
    ]
    finish = models.CharField(max_length=10, choices=FINITION_CHOICES)
    
    quantity = models.PositiveIntegerField()

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


class Commande(models.Model):
    utilisateur = models.ForeignKey("Utilisateurs", on_delete=models.CASCADE)
    configuration = models.OneToOneField(ConfigurationImpression, on_delete=models.CASCADE)
    date_commande = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=100)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    mode_paiement = models.CharField(max_length=155)

    def __str__(self):
        return f"Commande {self.id} - {self.utilisateur}"


def fichier_upload_path(instance, filename):
    # Stocke le fichier dans media/fichiers/<commande_id>/<filename>
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
        # Vérification de la résolution
        if self.resolution_dpi not in [150, 300]:
            raise ValidationError("La résolution doit être 150dpi ou 300dpi.")

        # Vérification du profil couleur
        if self.profil_couleur.upper() not in ["CMJN", "CYMK"]:
            raise ValidationError("Le profil couleur doit être CMJN ou CYMK.")

        # Vérification du format
        valid_extensions = ['.pdf', '.jpg', '.jpeg']
        if not any(self.fichier.name.lower().endswith(ext) for ext in valid_extensions):
            raise ValidationError("Le fichier doit être au format .pdf ou .jepg")

    def __str__(self):
        return self.nom_fichier


class Paiement(models.Model):
    commande = models.ForeignKey("Commande", on_delete=models.CASCADE, related_name="paiements")
    phone = models.CharField(max_length=15)  # numéro de téléphone pour le paiement
    montant = models.DecimalField(max_digits=15, decimal_places=2)  # montant en Ariary
    options = models.TextField(blank=True, null=True)  # options supplémentaires
    reference_trans = models.CharField(max_length=100, blank=True, null=True)  # référence de paiement Mvola
    date_paiement = models.DateTimeField(auto_now_add=True)
    statut_paiement = models.CharField(max_length=50, default="EN_ATTENTE")  # EN_ATTENTE, REUSSI, ECHOUE

    def __str__(self):
        return f"Paiement {self.reference_trans or self.id} - {self.statut_paiement}"



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

