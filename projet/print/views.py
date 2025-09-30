from rest_framework.permissions import IsAuthenticated, BasePermission, AllowAny
from decimal import Decimal
from rest_framework import viewsets
from .models import Produits, Utilisateurs, ConfigurationImpression, Commande, Fichier, Paiement
from .serializers import MyTokenObtainPairSerializer, ProduitsSerializer, ProfilSerializer, UserRegisterSerializer, UsersList, CommandeSerializer, CommandeAdminSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView 
from rest_framework.views import APIView
from rest_framework import generics, permissions
from django.db import transaction
import requests
from rest_framework.decorators import api_view, permission_classes
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404



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
    permission_classes = [AllowAny]  # 👈 force DRF à ignorer la règle globale

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Utilisateur créé avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# Affiché tout les utilisteur via react c'est une api
class UsersListView(APIView):
    permission_classes = [IsAuthenticated]  # Ajoutez cette ligne

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
            largeur = data.get("largeur")
            hauteur = data.get("hauteur")
            config = ConfigurationImpression.objects.create(
                format_type=data["format_type"],
                small_format=data.get("small_format") or None,
                largeur=Decimal(largeur) if largeur not in [None, ""] else None,
                hauteur=Decimal(hauteur) if hauteur not in [None, ""] else None,
                paper_type=data.get("paper_type") or None,
                finish=data.get("finish") or None,
                quantity=quantity,
                duplex=data.get("duplex") or None,
                binding=data.get("binding") or None,
                cover_paper=data.get("cover_paper") or None,
                options=data.get("options") or None,
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
    

# Pour récuper tout les commandes user
@api_view(['GET'])
@permission_classes([IsAuthenticated])  # L'utilisateur doit être authentifié
def get_user_commandes(request):
    user = request.user  # Récupère l'utilisateur connecté
    commandes = Commande.objects.filter(utilisateur=user, is_deleted=False).order_by('-date_commande')  # Filtre par utilisateur
    serializer = CommandeSerializer(commandes, many=True)  # Utilise le serializer mis à jour
    return Response(serializer.data, status=status.HTTP_200_OK)



# Deplacer la commande dans la corbeil
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def soft_delete_commande(request, id):
    try:
        # Si admin, pas besoin de filtrer par utilisateur
        if request.user.is_staff:  
            commande = Commande.objects.get(id=id)
        else:
            commande = Commande.objects.get(id=id, utilisateur=request.user)

        commande.is_deleted = True
        commande.save()
        return Response({"success": True, "message": "Commande déplacée vers la corbeille"})
    except Commande.DoesNotExist:
        return Response({"success": False, "message": "Commande introuvable"}, status=404)

    

# Récupérer les commandes dans la corbeille restaurer
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_commande(request, id):
    try:
        if request.user.is_staff:
            commande = Commande.objects.get(id=id)
        else:
            commande = Commande.objects.get(id=id, utilisateur=request.user)
        commande.is_deleted = False
        commande.save()
        return Response({"success": True, "message": "Commande restaurée"})
    except Commande.DoesNotExist:
        return Response({"success": False, "message": "Commande introuvable"}, status=404)



# Supprimer définitivement la commande
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_commande_forever(request, id):
    try:
        if request.user.is_staff:
            commande = Commande.objects.get(id=id)
        else:
            commande = Commande.objects.get(id=id, utilisateur=request.user)
        commande.delete()
        return Response({"success": True, "message": "Commande supprimée définitivement"})
    except Commande.DoesNotExist:
        return Response({"success": False, "message": "Commande introuvable"}, status=404)
    

# Récuperer les commandes supprimé , pour affiché dans la corbeil
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_deleted_commandes(request):
    """
    Récupère les commandes supprimées (soft deleted).
    - Si admin : toutes les commandes supprimées
    - Sinon : uniquement celles de l'utilisateur connecté
    """
    if request.user.is_staff:
        deleted_commandes = Commande.objects.filter(is_deleted=True).order_by('-date_commande')
    else:
        deleted_commandes = Commande.objects.filter(utilisateur=request.user, is_deleted=True).order_by('-date_commande')

    serializer = CommandeAdminSerializer(deleted_commandes, many=True)
    return Response(serializer.data)





# Récuperer tout les commandes côté admin
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_commandes_admin(request):
    try:
        # 🔹 Exclure les commandes soft deleted
        commandes = Commande.objects.filter(is_deleted=False).order_by('-date_commande')
        serializer = CommandeAdminSerializer(commandes, many=True)
        return Response(serializer.data)
    except Exception as e:
        import traceback
        return Response({"error": str(e), "trace": traceback.format_exc()}, status=500)



# Pour la notification
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_notification(request):
    """
    Admin peut envoyer une notification à un utilisateur
    """
    user_id = request.data.get("userId")
    message = request.data.get("message")

    if not user_id or not message:
        return Response({"error": "userId et message sont requis"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = Utilisateurs.objects.get(id=user_id)
        # Ici tu peux enregistrer la notification dans ta DB ou l'envoyer par mail/SMS/etc
        # Exemple simple : on stocke juste dans un modèle Notification
        # Notification.objects.create(user=user, message=message)
        
        # Pour test on renvoie juste un message
        return Response({"success": True, "message": f"Notification envoyée à {user.email}"}, status=status.HTTP_200_OK)
    except Utilisateurs.DoesNotExist:
        return Response({"error": "Utilisateur introuvable"}, status=status.HTTP_404_NOT_FOUND)


# Pour télecharger un fichier
def download_file(request, fichier_id):
    fichier_obj = get_object_or_404(Fichier, id=fichier_id)
    try:
        response = FileResponse(fichier_obj.fichier.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{fichier_obj.nom_fichier}"'
        return response
    except FileNotFoundError:
        raise Http404("Fichier non trouvé")


# Modifier les profils de l'utilisateur
class ProfilView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfilSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user # retourné l'utilisateur connécté


# Mofifié un mot de passe
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, *args, **kwargs):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not user.check_password(old_password):
            return Response({"error": "Ancien mot de passe incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"success": "Mot de passe changé avec succès"}, status=status.HTTP_200_OK)


# Pour le nombre total de commandes 
@api_view(['GET'])
@permission_classes([AllowAny])
def commandes_count_public(request):
    """
    Renvoie uniquement le nombre total de commandes (accessible publiquement).
    """
    try:
        total = Commande.objects.filter(is_deleted=False).count()
        return Response({"count": total})
    except Exception as e:
        import traceback
        return Response({"error": str(e), "trace": traceback.format_exc()}, status=500)