from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChangePasswordView, ProduitsViewSet, ProfilPhotoView, ProfilView, RegisterUserView, UsersListView, MyTokenObtainPairView, admin_dashboard_stats, changer_statut_commande, chatbot, commande_en_cours, commandes_count_public, delete_notification_forever, download_file, get_deleted_notifications, get_sent_notifications, google_login, mark_notifications_read, notifications_admin, restore_notification, search_products, send_notification_to_admin, send_notification_user, soft_delete_notification, terminer_commande, unread_count, user_dashboard_stats, user_notifications
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
    path('download/<int:fichier_id>/', download_file, name='download_file'),
    # Modifier le profil de l'utilisateur
    path('api/profil/', ProfilView.as_view(), name='profil'),
    path('api/profil/photo/', ProfilPhotoView.as_view(), name='profil-photo'),
    path('api/profil/change-password/', ChangePasswordView.as_view(), name="change-password"),
    path('api/admin/commandes/count/', commandes_count_public, name="nombre-commande"),
    # Permet d'envoyé la notification aux utilisateur que son commande est prêt à livré
    path("api/commandes/<int:commande_id>/terminer/", terminer_commande, name="terminer_commande"),
    # Permet d'envoyé la notification aux utilisateur que son commande est en cours de traitement
    path("api/commandes/<int:commande_id>/encours/", commande_en_cours, name="commande_en_cours"),
    # Permet d'envoyé la notification côté admin
    path("api/send-notification/", send_notification_user, name='envoie_notification'),
    # Récupérer les notifications côté user
    path("api/notifications/", user_notifications, name="user_notifications"),
    # Envoyé des notifications aux admin
    path("api/send-notification-admin/", send_notification_to_admin, name="send_notification_admin"),
    path('api/sent-notifications/', get_sent_notifications, name='get_sent_notifications'),
    # Récupérer les notification côté admin
    path("api/notifications-admin/", notifications_admin, name="notifications_admin"),
    # Récupérer le nombre de notifications non lues pour l'utilisateur connecté
    path("api/unread-count/", unread_count, name="nombre_notifications_non_lues"),
    # Marquer les notifications comme lues
    path("api/mark-notifications-read/", mark_notifications_read, name="marquer_notifications_comme_lues"),
    # Déplacer les notifications dans la corbeille côté admin/user
    path("api/notifications/delete/<int:id>/", soft_delete_notification),
    # Récupérer les notifications supprimé et affiché dans la corbeill côté admin/user
    path("api/notifications/deleted/", get_deleted_notifications),
    # Supprimer définitivement une notification côté admin/user
    path("api/notifications/delete-forever/<int:id>/", delete_notification_forever),
    # Réstaurer une notification côté admin/
    path("api/notifications/restore/<int:id>/", restore_notification),
    # Tableau de bord user
    path("api/user/dashboard-stats/", views.user_dashboard_stats, name="user_stats"),
    # Permet d'envoyé le lien vers l'email de l'user
    path("api/mot-de-passe-oublie/", views.mot_de_passe_oublie, name="mot_de_passe_oublie"),
    # Réinitialisé le mot de passe
    path("api/reinitialiser-mot-de-passe/<uidb64>/<token>/", views.reinitialiser_mot_de_passe, name="reinitialiser_mot_de_passe"),
    # Pour affiché un tableau de bord côté utilisteur
    path("api/user/dashboard-stats/", user_dashboard_stats, name="user_stats"),
    # Pour affiché un tableau de bord côté admin
    path('api/admin/dashboard/', admin_dashboard_stats, name='admin-dashboard'),
    # Modifié le status de la commande
    path("commandes/<int:commande_id>/update_statut/", changer_statut_commande),
    # Recherche
    path('api/search-produits/', search_products, name='search-produits'),
    # Login avec compte e-mail
    path('api/google-login/', google_login, name='google-login'),
    # Chat bot
    path("api/chatbot/", chatbot, name="chatbot"),

]    
