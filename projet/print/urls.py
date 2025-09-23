from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProduitsViewSet, RegisterView, UsersListView

router = DefaultRouter()
router.register(r'produits', ProduitsViewSet, basename='produits')

urlpatterns = [
    path('api/', include(router.urls)),
    # on appelle la vue sous forme de classe.
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/users/', UsersListView.as_view(), name='userList')
]
