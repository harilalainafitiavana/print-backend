from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProduitsViewSet, RegisterUserView, UsersListView, MyTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import MeView
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
]
