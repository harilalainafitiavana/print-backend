from rest_framework import viewsets
from .models import Produits, Utilisateurs
from .serializers import ProduitsSerializer, UsersList, UtilisateursSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

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
class RegisterView(APIView):
    def post(self, request):
        serializer = UtilisateursSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Inscription réussie"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# Affiché tout les utilisteur via react c'est une api
class UsersListView(APIView):
    def get(self, request):
        users = Utilisateurs.objects.all().order_by('-date_inscription')  # derniers inscrits en premier
        serializer = UsersList(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
