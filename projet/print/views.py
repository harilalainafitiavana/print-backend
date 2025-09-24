from decimal import Decimal
from rest_framework import viewsets
from .models import Produits, Utilisateurs, ConfigurationImpression, Commande, Fichier, Paiement
from .serializers import MyTokenObtainPairSerializer, ProduitsSerializer, UserRegisterSerializer, UsersList
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView 
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework import generics
from django.db import transaction
import requests
from rest_framework.decorators import api_view, permission_classes

# Ici ModelViewSet génère automatiquement les routes pour CRUD: GET/POST/PUT/DELETE
# GET /api/produits/ → liste les produits
# POST /api/produits/ → ajoute un produit
# GET /api/produits/1/ → détail d’un produit
# PUT /api/produits/1/ → modifier un produit
# DELETE /api/produits/1/ → supprimer un produit

# Permission personnalisée : seulement ADMIN peut modifier
class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        # Tout le monde peut lire (GET, HEAD, OPTIONS)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        # Mais pour écrire, il faut être connecté + role ADMIN
        return request.user.is_authenticated and getattr(request.user, "role", None) == "ADMIN"


class ProduitsViewSet(viewsets.ModelViewSet):
    queryset = Produits.objects.all()
    serializer_class = ProduitsSerializer
    permission_classes = [IsAdminOrReadOnly]



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



# backend/print/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_commande(request):
    data = request.data
    user = request.user  # L'utilisateur authentifié sera utilisé ici
    print("Utilisateur authentifié :", request.user)
    print("Type de l'utilisateur :", type(request.user))

    try:
        with transaction.atomic():
            # Validation de la quantité
            try:
                quantity = int(data.get("quantity", 0))  # Convertir en entier
            except ValueError:
                return Response({"success": False, "error": "La quantité doit être un nombre entier."}, status=400)

            # 1️⃣ Configuration de l'impression
            config = ConfigurationImpression.objects.create(
                format_type=data["format_type"],
                small_format=data.get("small_format") or None,
                largeur=Decimal(data.get("largeur")) if data.get("largeur") else None,
                hauteur=Decimal(data.get("hauteur")) if data.get("hauteur") else None,
                paper_type=data.get("paper_type"),
                finish=data.get("finish"),
                quantity=quantity,
                duplex=data.get("duplex") or None,
                binding=data.get("binding") or None,
                cover_paper=data.get("cover_paper") or None,
            )

            # 2️⃣ Commande
            montant_total = Decimal(quantity) * Decimal("500")  # Exemple prix unitaire = 500 Ar
            commande = Commande.objects.create(
                utilisateur=user,  # Utilisez l'utilisateur authentifié
                montant_total=montant_total,
                configuration=config,
            )

            # 3️⃣ Fichiers
            uploaded_file = request.FILES.get("file")  # récupère le fichier envoyé depuis React
            if uploaded_file:
                Fichier.objects.create(
                    commande=commande,
                    nom_fichier=request.data.get("fileName", uploaded_file.name),
                    fichier=uploaded_file,
                    format=request.data.get("file_format", ""), 
                    taille=request.data.get("quantity", ""),
                    resolution_dpi=request.data.get("dpi", ""),
                    profil_couleur=request.data.get("colorProfile", ""),
                )
                        # 4️⃣ Paiement via Mvola Test
            # mvola_response = requests.post(
            #     "https://api-mvola-test.com/payment",
            #     json={
            #         "phone": data["phone"],
            #         "amount": float(montant_total),  # <-- converti en float
            #         "order_id": commande.id
            #     },
            #     headers={"Authorization": "Bearer TEST_TOKEN"}
            # ).json()
            mvola_response = {
                "transaction_id": f"TEST-{commande.id}",
                "status": "pending"
            }

            Paiement.objects.create(
                commande=commande,
                phone=data["phone"],
                montant=montant_total,
                transaction_id=mvola_response.get("transaction_id"),
                statut_paiement=mvola_response.get("status", "pending")
            )

        return Response({
            "success": True,
            "commande_id": commande.id, "paiement_status": mvola_response.get("status"),
            "montant_total": float(montant_total)
        })

    except Exception as e:
        return Response({"success": False, "error": str(e)})
    

    ...
