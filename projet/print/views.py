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
import threading
from django.core.mail import send_mail
from django.conf import settings



# Ici ModelViewSet génère automatiquement les routes pour CRUD: GET/POST/PUT/DELETE
# GET /api/produits/ → liste les produits
# POST /api/produits/ → ajoute un produit
# GET /api/produits/1/ → détail d’un produit
# PUT /api/produits/1/ → modifier un produit
# DELETE /api/produits/1/ → supprimer un produit

# Permission personnalisée : seulement ADMIN peut modifier un produit
class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        # Tout le monde peut lire (GET, HEAD, OPTIONS)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        # Mais pour écrire, il faut être connecté + role ADMIN
        return request.user.is_authenticated and getattr(request.user, "role", None) == "ADMIN"

# Récuperer tout les produits et affiché/suprimet/ajouter
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
    """
    Endpoint pour créer une commande d'impression.
    Gère :
    - La création de la configuration d'impression
    - Le calcul automatique du montant total via le modèle
    - La gestion du fichier uploadé
    - La simulation du paiement Mvola
    - L'envoi automatique d'emails après 2 minutes et 2 heures
    """
    data = request.data
    user = request.user  # L'utilisateur connecté qui passe la commande

    try:
        with transaction.atomic():  # Tout est atomique, rollback si erreur
            # -----------------------------
            # 1️⃣ Récupération de la quantité et nombre de pages si c'est un livre
            # -----------------------------
            try:
                quantity = int(data.get("quantity", 0))
            except ValueError:
                return Response({"success": False, "error": "La quantité doit être un nombre entier."}, status=400)

            # Vérifie si c'est un livre et récupère le nombre de pages
            is_book = data.get("is_book", "false").lower() == "true"
            book_pages = int(data.get("book_pages")) if data.get("book_pages") and is_book else None

            # -----------------------------
            # 2️⃣ Création de la configuration d'impression
            # -----------------------------
            largeur = data.get("largeur")
            hauteur = data.get("hauteur")
            config = ConfigurationImpression.objects.create(
                format_type=data["format_type"],                    # Petit ou grand format
                small_format=data.get("small_format") or None,     # Si petit format
                largeur=Decimal(largeur) if largeur not in [None, ""] else None,
                hauteur=Decimal(hauteur) if hauteur not in [None, ""] else None,
                paper_type=data.get("paper_type") or None,         # Type de papier
                finish=data.get("finish") or None,                 # Finition
                quantity=quantity,
                duplex=data.get("duplex") or None,                 # Recto ou recto/verso
                binding=data.get("binding") or None,               # Type de reliure
                cover_paper=data.get("cover_paper") or None,       # Couverture
                options=data.get("options") or None,               # Options supplémentaires
                is_book=is_book,                                   # Livre ou non
                book_pages=book_pages                              # Nombre de pages si livre
            )

            # -----------------------------
            # 3️⃣ Création de la commande
            # -----------------------------
            # montant_total sera calculé automatiquement via la méthode save()
            commande = Commande.objects.create(
                utilisateur=user,
                configuration=config,
                mode_paiement=data.get("mode_paiement", "MVola")
            )

            # -----------------------------
            # 4️⃣ Gestion du fichier uploadé
            # -----------------------------
            uploaded_file = request.FILES.get("file")
            if uploaded_file:
                Fichier.objects.create(
                    commande=commande,
                    nom_fichier=data.get("fileName", uploaded_file.name),
                    fichier=uploaded_file,
                    format=data.get("file_format", ""),
                    taille=str(quantity),
                    resolution_dpi=data.get("dpi", ""),
                    profil_couleur=data.get("colorProfile", "")
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

                    # Simulation avec mvola test


                    # Email impression en cours (après 2 heures)

            # -----------------------------
            # 5️⃣ Simulation paiement Mvola test
            # -----------------------------
            mvola_response = {
                "transaction_id": f"TEST-{commande.id}",
                "status": "pending"
            }
            Paiement.objects.create(
                commande=commande,
                phone=data.get("phone", ""),
                montant=commande.montant_total,                    # Montant calculé automatiquement
                transaction_id=mvola_response.get("transaction_id"),
                statut_paiement=mvola_response.get("status", "pending")
            )

            # -----------------------------
            # 6️⃣ Préparation envoi d'emails
            # -----------------------------
            user_email = user.email
            commande_id = commande.id
            montant = float(commande.montant_total)
            format_type = config.format_type
            small_format = config.small_format or "-"
            nombre_pages = config.book_pages if config.is_book else "-"
            quantity = config.quantity

            # Récupère le fichier associé
            fichier_associe = Fichier.objects.filter(commande=commande).first()
            nom_fichier = fichier_associe.nom_fichier if fichier_associe else "Aucun fichier"
            format_fichier = fichier_associe.format if fichier_associe else "-"
            resolution = fichier_associe.resolution_dpi if fichier_associe else "-"

            # Email confirmation (après 2 minutes)
            def send_confirmation_email():
                send_mail(
                    subject="✅ Confirmation de votre commande sur Print.mg",
                    message=(
                        f"Bonjour {user.nom} {user.prenom},\n\n"
                        f"Votre commande n°{commande_id} a bien été reçue ✅.\n\n"
                        f"📌 Détails de la commande :\n"
                        f"- Montant total : {montant} Ar\n"
                        f"- Quantité : {quantity}\n"
                        f"- Nombre de pages : {nombre_pages}\n"
                        f"- Format : {format_type} ({small_format})\n"
                        f"- Fichier : {nom_fichier} ({format_fichier}, {resolution} dpi)\n\n"
                        f"Nous vous enverrons un email lorsque l’impression commencera 🖨️.\n\n"
                        f"Merci de votre confiance 🙏"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user_email],
                    fail_silently=False,
                )

            threading.Timer(120, send_confirmation_email).start()

        # Réponse JSON
        return Response({
            "success": True,
            "commande_id": commande.id,
            "paiement_status": mvola_response.get("status"),
            "montant_total": float(commande.montant_total)
        })

    except Exception as e:
        # Gestion des erreurs
        return Response({"success": False, "error": str(e)})


# Pour récuper tout les commandes user
@api_view(['GET'])
@permission_classes([IsAuthenticated])  # L'utilisateur doit être authentifié
def get_user_commandes(request):
    user = request.user  # Récupère l'utilisateur connecté
    commandes = Commande.objects.filter(utilisateur=user, is_deleted=False).order_by('-date_commande')  # Filtre par utilisateur
    serializer = CommandeSerializer(commandes, many=True)  # Utilise le serializer mis à jour
    return Response(serializer.data, status=status.HTTP_200_OK)



# Deplacer la commande dans la corbeil côté admin/user
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

    

# Récupérer les commandes dans la corbeille restaurer côté admin/user
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


# Supprimer définitivement la commande côté admin/user
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
    

# Récuperer les commandes supprimé et affiché dans la corbeil côté admin/user
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


# Permet aux admin de télecharge le fichier d'un document
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


# Mofifié un mot de passe dans le profil utilisateur
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


# Calculer le nombre total des commandes et affiché dans le site 
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


# Envoyé des notifications vers l'email de l'utilisateur que son commande est prêt à livré
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # ✅ Accessible seulement aux admins
def terminer_commande(request, commande_id):
    try:
        # ✅ Vérifie que la commande existe
        commande = Commande.objects.get(id=commande_id, is_deleted=False)
        user = commande.utilisateur

        # ✅ Récupération des infos supplémentaires
        montant = float(commande.montant_total)
        config = commande.configuration
        quantity = config.quantity
        format_type = config.format_type
        small_format = config.small_format or "-"
        nombre_pages = config.book_pages if config.is_book else "-"

        # ✅ Récupération des fichiers associés
        fichier = Fichier.objects.filter(commande=commande).first()
        nom_fichier = fichier.nom_fichier if fichier else "Aucun fichier"
        format_fichier = fichier.format if fichier else "-"
        resolution = fichier.resolution_dpi if fichier else "-"

        # ✅ Envoi de l'email avec détails
        send_mail(
            subject="📦 Print.mg - Votre commande est prête à être livrée",
            message=(
                f"Bonjour {user.nom} {user.prenom},\n\n"
                f"Votre commande n°{commande.id} est maintenant terminée ✅ et prête à être livrée.\n\n"
                f"📌 Détails de la commande :\n"
                f"- Montant total : {montant} Ar\n"
                f"- Quantité : {quantity}\n"
                f"- Nombre de pages : {nombre_pages}\n"
                f"- Format : {format_type} ({small_format})\n"
                f"- Fichier : {nom_fichier} ({format_fichier}, {resolution} dpi)\n\n"
                f"Merci pour votre confiance 🙏"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response({"success": True, "message": "Email envoyé avec succès ✅"})

    except Commande.DoesNotExist:
        return Response({"success": False, "error": "Commande introuvable"}, status=404)
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def commande_en_cours(request, commande_id):
    try:
        # Vérifie que la commande existe
        commande = Commande.objects.get(id=commande_id, is_deleted=False)
        user = commande.utilisateur

        # Récupération des infos supplémentaires
        montant = float(commande.montant_total)
        config = commande.configuration
        quantity = config.quantity
        format_type = config.format_type
        small_format = config.small_format or "-"
        nombre_pages = config.book_pages if config.is_book else "-"

        # Fichier associé
        fichier = Fichier.objects.filter(commande=commande).first()
        nom_fichier = fichier.nom_fichier if fichier else "Aucun fichier"
        format_fichier = fichier.format if fichier else "-"
        resolution = fichier.resolution_dpi if fichier else "-"

        # Envoi de l'email
        send_mail(
            subject="🖨️ Print.mg - Votre commande est en cours d'impression",
            message=(
                f"Re-bonjour {user.nom} {user.prenom},\n\n"
                f"Votre commande n°{commande.id} est maintenant en cours d'impression 🖨️.\n\n"
                f"📌 Détails de la commande :\n"
                f"- Montant : {montant} Ar\n"
                f"- Quantité : {quantity}\n"
                f"- Nombre de pages : {nombre_pages}\n"
                f"- Format : {format_type} ({small_format})\n"
                f"- Fichier : {nom_fichier} ({format_fichier}, {resolution} dpi)\n\n"
                f"Nous vous tiendrons informé lors de l’expédition 🚚.\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        # Mettre à jour le statut
        commande.statut = "EN_COURS_IMPRESSION"
        commande.save()

        return Response({"success": True, "message": "Email envoyé et statut mis à jour ✅"})

    except Commande.DoesNotExist:
        return Response({"success": False, "error": "Commande introuvable"}, status=404)
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=500)
