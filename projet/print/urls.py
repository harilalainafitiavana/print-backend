from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChangePasswordView, ProduitsViewSet, ProfilView, RegisterUserView, UsersListView, MyTokenObtainPairView, commande_en_cours, commandes_count_public, download_file, terminer_commande
from rest_framework_simplejwt.views import TokenRefreshView
from .views import MeView, get_user_commandes
from . import views

router = DefaultRouter()
router.register(r'produits', ProduitsViewSet, basename='produits')

urlpatterns = [
    path('api/', include(router.urls)),
    # on appelle la vue sous forme de classe.
    path('api/register/', RegisterUserView.as_view(), name='register'),
    path('api/users/', UsersListView.as_view(), name='userList'),
    # Token pour le login de connexion
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Route pour obtenir les informations de l'utilisateur connecté
    path('api/me/', MeView.as_view(), name='me'),
    # Route pour créer une commande
    path('api/commande/', views.create_commande, name='create_commande'),
    # Affiché les commandes
    path('api/commandes/', get_user_commandes, name='get_user_commandes'),
    # Supprimer le commande dans la corbeille
    path('api/commandes/<int:id>/soft_delete/', views.soft_delete_commande),
    # Récupérer les produits supprimés pour affiché dans la crobeille 
    path('api/commandes/deleted/', views.get_deleted_commandes),
    # Restaurer ou supprimer définitivement une commande
    path('api/commandes/<int:id>/restore/', views.restore_commande),
    path('api/commandes/<int:id>/delete_forever/', views.delete_commande_forever),
    # Récupérer tout les commandes côté admin
    path('api/admin/commandes/', views.get_all_commandes_admin, name='admin_commandes'),
    path('api/notify/', views.send_notification, name='send_notification'),
    path('download/<int:fichier_id>/', download_file, name='download_file'),
    # Modifier le profil de l'utilisateur
    path('api/profil/', ProfilView.as_view(), name='profil'),
    path('api/profil/change-password/', ChangePasswordView.as_view(), name="change-password"),
    path('api/admin/commandes/count/', commandes_count_public, name="nombre-commande"),
    # Permet d'envoyé la notification aux utilisateur que son commande est prêt à livré
    path("api/commandes/<int:commande_id>/terminer/", terminer_commande, name="terminer_commande"),
    # Permet d'envoyé la notification aux utilisateur que son commande est en cours de traitement
    path("api/commandes/<int:commande_id>/encours/", commande_en_cours, name="commande_en_cours")
]
