from rest_framework import viewsets
from .models import Produits, Utilisateurs
from .serializers import MyTokenObtainPairSerializer, ProduitsSerializer, UserRegisterSerializer, UsersList
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView 
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics


# Ici ModelViewSet génère automatiquement les routes pour CRUD: GET/POST/PUT/DELETE
# GET /api/produits/ → liste les produits
# POST /api/produits/ → ajoute un produit
# GET /api/produits/1/ → détail d’un produit
# PUT /api/produits/1/ → modifier un produit
# DELETE /api/produits/1/ → supprimer un produit
class ProduitsViewSet(viewsets.ModelViewSet):
    queryset = Produits.objects.all()
    serializer_class = ProduitsSerializer


# Insérer l'utilisateur dans la base c'est une api
class RegisterUserView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Utilisateur créé avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# Affiché tout les utilisteur via react c'est une api
class UsersListView(APIView):
    def get(self, request):
        users = Utilisateurs.objects.all().order_by('-date_inscription')  # derniers inscrits en premier
        serializer = UsersList(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

# Token pour le login de connexion
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


# Récuperation des informations de l'utiliateur api
class MeView(APIView):
    permission_classes = [IsAuthenticated]  # 🔹 L’utilisateur doit être authentifié

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "nom": user.nom,
            "prenom": user.prenom,
            "email": user.email,
            "role": user.role,
            "profils": user.profils.url if user.profils else None,
        })
