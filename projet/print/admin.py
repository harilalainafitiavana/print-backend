from django.contrib import admin
from .models import (
    Notification, Produits, Utilisateurs, ConfigurationImpression,
    Commande, Fichier, Paiement, Chat, Contenir, Communiquer
)
from django.contrib.auth.admin import UserAdmin

# --------- Produits ----------
@admin.register(Produits)
class ProduitsAdmin(admin.ModelAdmin):
    list_display = ("name", "categorie", "prix", "future", "image")
    search_fields = ("name", "categorie")
    list_filter = ("categorie",)

# --------- Utilisateurs ----------
class UtilisateursAdmin(UserAdmin):
    model = Utilisateurs
    list_display = ('email', 'nom', 'prenom', 'role', 'is_staff', 'is_active', 'code_postal', 'ville', 'pays')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'nom', 'prenom')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'nom', 'prenom', 'password')}),
        ('Permissions', {'fields': ('role', 'is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nom', 'prenom', 'password1', 'password2', 'role', 'is_staff', 'is_active')}
        ),
    )

admin.site.register(Utilisateurs, UtilisateursAdmin)

# --------- Configuration Impression ----------
@admin.register(ConfigurationImpression)
class ConfigurationImpressionAdmin(admin.ModelAdmin):
    list_display = ("format_type", "small_format", "largeur", "hauteur", "paper_type", "finish", "quantity", "duplex", "binding", "cover_paper")
    list_filter = ("format_type", "paper_type", "finish")
    search_fields = ("small_format",)

# --------- Commande ----------
@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ("id", "utilisateur", "date_commande", "statut", "montant_total", "mode_paiement")
    list_filter = ("statut", "mode_paiement")
    search_fields = ("utilisateur__nom", "utilisateur__prenom", "id")

# --------- Fichier ----------
@admin.register(Fichier)
class FichierAdmin(admin.ModelAdmin):
    list_display = ("nom_fichier", "commande", "format", "taille", "resolution_dpi", "profil_couleur", "date_upload", "fichier")
    search_fields = ("nom_fichier", "commande__id")
    list_filter = ("format",)

# --------- Paiement ----------
@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("commande", "phone", "montant", "statut_paiement", "date_paiement")
    list_filter = ("statut_paiement", "date_paiement")
    search_fields = ("commande__id", "phone", "reference_trans")

# --------- Chat ----------
@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "type_message", "date_message", "message_preview")
    list_filter = ("type_message",)
    search_fields = ("utilisateur__nom", "message")

    def message_preview(self, obj):
        return obj.message[:50] + ("..." if len(obj.message) > 50 else "")
    message_preview.short_description = "Message"

# --------- Contenir ----------
@admin.register(Contenir)
class ContenirAdmin(admin.ModelAdmin):
    list_display = ("commande", "fichier")
    search_fields = ("commande__id", "fichier__nom_fichier")

# --------- Communiquer ----------
@admin.register(Communiquer)
class CommuniquerAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "message")
    search_fields = ("utilisateur__nom", "message__message")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user','sender', 'message', 'is_read', 'created_at')  # colonnes visibles dans la liste
    list_filter = ('is_read', 'created_at')  # filtres sur le côté
    search_fields = ('user__nom', 'user__prenom', 'user__email', 'message')  # barre de recherche
    readonly_fields = ('created_at',)  # champ en lecture seule