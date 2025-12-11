from rest_framework.permissions import IsAuthenticated, BasePermission, AllowAny
from decimal import Decimal
from rest_framework import viewsets
from .models import Notification, Produits, Utilisateurs, ConfigurationImpression, Commande, Fichier, Paiement
from .serializers import MyTokenObtainPairSerializer, NotificationSerializer, ProduitsSerializer, ProfilSerializer, UserRegisterSerializer, UsersList, CommandeSerializer, CommandeAdminSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView 
from rest_framework.views import APIView
from rest_framework import generics, permissions
from django.db import transaction
import requests
from rest_framework.decorators import api_view, permission_classes
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
import threading
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, F, Value
from django.db.models.functions import TruncMonth
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils.http import urlsafe_base64_decode
import re
from django.db.models import Q
from rest_framework_simplejwt.tokens import RefreshToken
import os
import time
from decouple import config
from transformers import pipeline, AutoTokenizer, AutoModelForQuestionAnswering

# from django.db.models.functions import Func
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
            "profils": user.google_avatar_url if user.google_avatar_url else (user.profils.url if user.profils else None),
        })


# backend/print/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_commande(request):
    """
    Endpoint pour créer une commande d'impression.
    """
    data = request.data
    user = request.user

    try:
        with transaction.atomic():
            # -----------------------------
            # 1️⃣ RÉCUPÉRATION DU PRODUIT (OPTIONNEL POUR LES LIVRES)
            # -----------------------------
            produit_id = data.get("produit_id")
            produit = None
            
            # ⭐ MODIFICATION : Produit obligatoire seulement si ce n'est pas un livre
            is_book = data.get("is_book", "false").lower() == "true"
            
            if not is_book and not produit_id:
                return Response({"success": False, "error": "Veuillez sélectionner un produit pour les impressions normales."}, status=400)
            
            if produit_id:
                try:
                    produit = Produits.objects.get(id=produit_id)
                except Produits.DoesNotExist:
                    if not is_book:
                        return Response({"success": False, "error": "Produit non trouvé."}, status=400)
                    # Pour les livres, on continue même si le produit n'existe pas

            # -----------------------------
            # 2️⃣ RÉCUPÉRATION DES DONNÉES
            # -----------------------------
            try:
                quantity = int(data.get("quantity", 0))
            except ValueError:
                return Response({"success": False, "error": "La quantité doit être un nombre entier."}, status=400)

            book_pages = int(data.get("book_pages")) if data.get("book_pages") and is_book else None

            # -----------------------------
            # 3️⃣ CRÉATION DE LA CONFIGURATION
            # -----------------------------
            largeur = data.get("largeur")
            hauteur = data.get("hauteur")
            config = ConfigurationImpression.objects.create(
                produit=produit,  # ⭐ Peut être None pour les livres
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
                is_book=is_book,
                book_pages=book_pages
            )

            # -----------------------------
            # 4️⃣ CRÉATION DE LA COMMANDE
            # -----------------------------
            commande = Commande.objects.create(
                utilisateur=user,
                configuration=config,
                mode_paiement=data.get("mode_paiement", "MVola")
            )

            # -----------------------------
            # 5️⃣ GESTION DU FICHIER UPLOADÉ
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

            # -----------------------------
            # 6️⃣ SIMULATION PAIEMENT Mvola
            # -----------------------------
            mvola_response = {
                "transaction_id": f"TEST-{commande.id}",
                "status": "pending"
            }
            Paiement.objects.create(
                commande=commande,
                phone=data.get("phone", ""),
                montant=commande.montant_total,
                transaction_id=mvola_response.get("transaction_id"),
                statut_paiement=mvola_response.get("status", "pending")
            )

            # -----------------------------
            # 7️⃣ PRÉPARATION ENVOI EMAILS
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
                type_commande = "Livre" if is_book else "Produit normal"
                produit_nom = produit.name if produit else "Livre (tarifs standard)"
                
                send_mail(
                    subject="✅ Confirmation de votre commande sur Print.mg",
                    message=(
                        f"Bonjour {user.nom} {user.prenom},\n\n"
                        f"Votre commande n°{commande_id} a bien été reçue ✅.\n\n"
                        f"📌 Détails de la commande :\n"
                        f"- Type: {type_commande}\n"
                        f"- Produit: {produit_nom}\n"
                        f"- Montant total : {montant} Ar\n"
                        f"- Quantité : {quantity}\n"
                        f"- Nombre de pages : {nombre_pages}\n"
                        f"- Format : {format_type} ({small_format})\n"
                        f"- Fichier : {nom_fichier} ({format_fichier}, {resolution} dpi)\n\n"
                        f"Nous vous enverrons un email lorsque l'impression commencera 🖨️.\n\n"
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
            "montant_total": float(commande.montant_total),
            "type": "livre" if is_book else "produit_normal"
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

# Modifier la photo de profil de l'utilisateur
class ProfilPhotoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def put(self, request):
        print("=" * 50)
        print("📸 ENDPOINT PHOTO DÉDIÉ")
        print("=" * 50)
        print(f"📦 FILES reçus: {dict(request.FILES)}")
        print(f"📦 User: {request.user.email}")
        
        user = request.user
        
        if 'profils' not in request.FILES:
            print("❌ AUCUN FICHIER dans request.FILES")
            return Response({"error": "Aucune image reçue"}, status=400)
        
        profils = request.FILES['profils']
        print(f"💾 Fichier reçu: {profils.name} ({profils.size} bytes)")
        print(f"📁 Ancien fichier: {user.profils}")
        
        # Supprimer l'ancien fichier
        if user.profils:
            try:
                user.profils.delete(save=False)
                print("🗑️ Ancien fichier supprimé")
            except Exception as e:
                print(f"⚠️ Erreur suppression: {e}")
        
        # Sauvegarder le nouveau
        user.profils = profils
        user.google_avatar_url = None  # Important
        user.save()
        
        print(f"✅ NOUVEAU FICHIER: {user.profils}")
        print(f"✅ URL: {user.profils.url}")
        
        return Response({
            "message": "Photo mise à jour", 
            "profils": user.profils.url
        })

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
                f"Nous vous envoyez une message à votre numéro téléphone pour la livraison\n"
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


# Envoyé le notification vers l'utilisateur concerné
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_notification_user(request):
    try:
        user_email = request.data.get("user_email")
        message = request.data.get("message")

        if not user_email or not message:
            return Response({"error": "user_email et message requis"}, status=400)

        try:
            selected_user = Utilisateurs.objects.get(email=user_email)
        except Utilisateurs.DoesNotExist:
            return Response({"error": "Utilisateur non trouvé"}, status=404)

        # Création de la notification
        notification = Notification.objects.create(
            sender=request.user,   # admin connecté
            user=selected_user,    # destinataire = utilisateur
            message=message
        )

        serializer = NotificationSerializer(notification)
        return Response(serializer.data)

    except Exception as e:
        print("❌ Erreur send_notification_to_user:", e)
        return Response({"error": "Impossible d’envoyer la notification"}, status=500)


# Récupére le notification selon l'utilisateur concerné
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_notifications(request):
    try:
        notifications = Notification.objects.filter(user=request.user, is_deleted=False).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
    except Exception as e:
        print("❌ Erreur fetch notifications:", e)
        return Response({"error": "Impossible de récupérer les notifications"}, status=500)


# Envoyé un notification vers l'admin
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_notification_to_admin(request):
    try:
        message = request.data.get("message")
        if not message:
            return Response({"error": "Message requis"}, status=400)

        # Récupérer un admin
        admin_user = Utilisateurs.objects.filter(role="ADMIN").first()
        if not admin_user:
            return Response({"error": "Admin non trouvé"}, status=404)

        # Créer la notification
        notification = Notification.objects.create(
            sender=request.user,   # utilisateur connecté
            user=admin_user,       # destinataire = admin
            message=message
        )

        serializer = NotificationSerializer(notification)
        return Response(serializer.data)

    except Exception as e:
        print("❌ Erreur send_notification_to_admin:", e)
        return Response({"error": "Impossible d’envoyer la notification"}, status=500)


# Récupérer les notifications que l'utilisateur à envoyé, pour affiché dans le dahboard admin
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_admin(request):
    notifications = Notification.objects.filter(sender__role="USER", is_deleted=False).order_by("-created_at")
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


# Endpoint ou api permet de récupérer les notifications non lues
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    try:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})
    except Exception as e:
        print("❌ Erreur unread_count:", e)
        return Response({"error": "Impossible de récupérer le nombre"}, status=500)


# Marquer une notification comme lue quand l'utilisteur clique sur l'icône de notification
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    try:
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"success": True})
    except Exception as e:
        print("❌ Erreur mark read:", e)
        return Response({"error": "Impossible de marquer comme lu"}, status=500)


# Déplacer les notifications dans la corbeille côté admin/user
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def soft_delete_notification(request, id):
    try:
        if request.user.is_staff:
            notif = Notification.objects.get(id=id)
        else:
            notif = Notification.objects.get(id=id, user=request.user)

        notif.is_deleted = True
        notif.save()
        return Response({"success": True, "message": "Notification déplacée dans la corbeille"})
    except Notification.DoesNotExist:
        return Response({"success": False, "message": "Notification introuvable"}, status=404)


# Récupérer les notifications supprimé et affiché dans la corbeill côté admin/user
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_deleted_notifications(request):
    if request.user.is_staff:
        deleted_notifs = Notification.objects.filter(is_deleted=True).order_by('-created_at')
    else:
        deleted_notifs = Notification.objects.filter(user=request.user, is_deleted=True).order_by('-created_at')

    serializer = NotificationSerializer(deleted_notifs, many=True)
    return Response(serializer.data)


# Supprimer définitivement une notification côté admin/user
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification_forever(request, id):
    try:
        if request.user.is_staff:
            notif = Notification.objects.get(id=id)
        else:
            notif = Notification.objects.get(id=id, user=request.user)

        notif.delete()
        return Response({"success": True, "message": "Notification supprimée définitivement"})
    except Notification.DoesNotExist:
        return Response({"success": False, "message": "Notification introuvable"}, status=404)


# Réstaurer une notification côté admin/
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_notification(request, id):
    try:
        if request.user.is_staff:
            notif = Notification.objects.get(id=id)
        else:
            notif = Notification.objects.get(id=id, user=request.user)

        notif.is_deleted = False
        notif.save()
        return Response({"success": True, "message": "Notification restaurée"})
    except Notification.DoesNotExist:
        return Response({"success": False, "message": "Notification introuvable"}, status=404)


# Api  pour tableau de bord utilisteur
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_dashboard_stats(request):
    user = request.user

    commandes = Commande.objects.filter(utilisateur=user, is_deleted=False)
    notifications = Notification.objects.filter(user=user, is_deleted=False)
    fichiers = Fichier.objects.filter(commande__utilisateur=user)

    total_commandes = commandes.count()
    montant_total = sum(c.montant_total for c in commandes)
    total_fichiers = fichiers.count()
    notifications_non_lues = notifications.filter(is_read=False).count()

    # Commandes et montants par mois
    commandes_par_mois = (
        commandes.annotate(mois=TruncMonth("date_commande"))
        .values("mois")
        .annotate(nombre=Count("id"), montant=Sum("montant_total"))
        .order_by("mois")
    )
    commandes_par_mois = [
        {"mois": c["mois"].strftime("%b %Y"), "nombre": c["nombre"], "montant": c["montant"] or 0}
        for c in commandes_par_mois
    ]

    dernières_commandes = commandes.order_by("-date_commande")[:5].values("id", "date_commande", "montant_total")
    dernières_notifications = notifications.order_by("-created_at")[:5].values("id", "message", "created_at")

    return Response({
        "user_email": user.email,
        "total_commandes": total_commandes,
        "montant_total": montant_total,
        "total_fichiers": total_fichiers,
        "notifications_non_lues": notifications_non_lues,
        "commandes_par_mois": commandes_par_mois,
        "dernières_commandes": list(dernières_commandes),
        "dernières_notifications": list(dernières_notifications),
    })


# Fonction pour l'envoie du lien vers l'email

# Générateur de token sécurisé pour la réinitialisation
token_generator = PasswordResetTokenGenerator()

@csrf_exempt  # ⚠️ Désactivation CSRF seulement en dev (React + localhost)
def mot_de_passe_oublie(request):
    """
    Vue pour gérer la demande de réinitialisation du mot de passe.
    L'utilisateur envoie son email, et s'il existe dans la base,
    un lien de réinitialisation est envoyé à son adresse.
    """

    # ✅ On autorise uniquement la méthode POST
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        # 🧾 Récupération des données envoyées par le frontend (JSON)
        data = json.loads(request.body)
        email = data.get("email", "").strip().lower()  # Normalisation de l'email

        if not email:
            return JsonResponse({"error": "Veuillez entrer une adresse email valide."}, status=400)

        # 🔍 Vérifie si un utilisateur existe avec cet email
        try:
            user = Utilisateurs.objects.get(email=email)
        except Utilisateurs.DoesNotExist:
            # ⚠️ Pour plus de sécurité, on ne révèle pas si l'email existe ou non.
            # (évite les attaques d'énumération d'utilisateurs)
            return JsonResponse({
                "message": "Si un compte est associé à cet email, un lien a été envoyé."
            })

        # 🔐 Génération d'un UID encodé et d'un token sécurisé et le token est dédruit automatique après avoir modifié le mot de passe
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)

        # 🌐 Création du lien de réinitialisation local pour le moment
        reset_link = f"http://localhost:5173/reset-password/{uid}/{token}"

        # ✉️ Envoi du mail de réinitialisation
        try:
            send_mail(
                subject="Réinitialisation du mot de passe",
                message=(
                    f"Bonjour {user.prenom} qui à l'adresse {user.email},\n\n"
                    f"Vous avez demandé à réinitialiser votre mot de passe.\n"
                    f"Cliquez sur le lien ci-dessous pour le faire :\n"
                    f"{reset_link}\n\n"
                    f"Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet email.\n\n"
                    f"Cordialement,\nL'équipe Print.mg"
                ),
                from_email=settings.EMAIL_HOST_USER,  # Adresse d’envoi configurée dans settings.py
                recipient_list=[email],  # Liste contenant une seule adresse ici
                fail_silently=False,  # En dev, on veut voir les erreurs
            )
        except Exception as e:
            # ⚠️ Si l'envoi échoue (ex: problème SMTP), on log et on informe le client
            print("Erreur lors de l'envoi de l'email:", e)
            return JsonResponse({"error": "Impossible d'envoyer l'email. Vérifiez la configuration SMTP."}, status=500)

        # ✅ Message final (toujours générique)
        return JsonResponse({
            "message": "Si un compte est associé à cet email, un lien de réinitialisation a été envoyé."
        })

    except json.JSONDecodeError:
        # ⚠️ Si le JSON est mal formé
        return JsonResponse({"error": "Format JSON invalide."}, status=400)

    except Exception as e:
        # 🚨 Pour tout autre cas inattendu (utile pendant le dev)
        print("Erreur inattendue:", e)
        return JsonResponse({"error": "Une erreur interne est survenue."}, status=500)


# Fonction pour la réinitialisation de mot de passe

# Générateur de token sécurisé 
token_generator = PasswordResetTokenGenerator()

@csrf_exempt  # ⚠️ CSRF désactivé pour le dev (React + localhost)
def reinitialiser_mot_de_passe(request, uidb64, token):

    # ✅ On n'accepte que la méthode POST
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        # 🧾 Récupération des données envoyées par React
        data = json.loads(request.body)
        password = data.get("password", "").strip() # Normalisation du mdp
        confirm_password = data.get("confirm_password", "").strip()

        # ⚠️ Vérifie que les deux mots de passe sont identiques
        if password != confirm_password:
            return JsonResponse({"error": "Les mots de passe ne correspondent pas."}, status=400)

        # ⚠️ Vérifie que le mot de passe n’est pas vide
        if not password:
            return JsonResponse({"error": "Le mot de passe ne peut pas être vide."}, status=400)

        # 🔐 Décodage de l'UID
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = Utilisateurs.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Utilisateurs.DoesNotExist):
            return JsonResponse({"error": "Lien invalide."}, status=400)

        # 🔑 Vérification du token
        if not token_generator.check_token(user, token):
            return JsonResponse({"error": "Lien invalide ou expiré."}, status=400)

        # 🔒 Vérification de la sécurité du mot de passe
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$'
        if not re.match(pattern, password):
            return JsonResponse({
                "error": (
                    "Le mot de passe doit contenir au moins 8 caractères, "
                    "une majuscule, une minuscule, un chiffre et un caractère spécial."
                )
            }, status=400)

        # ✅ Modification du mot de passe
        user.set_password(password)  # Hashage automatique du mot de passe
        user.save()

        # 📤 Réponse JSON
        return JsonResponse({"message": "Mot de passe réinitialisé avec succès."})

    except json.JSONDecodeError:
        # ⚠️ Si le JSON envoyé par React est invalide
        return JsonResponse({"error": "Format JSON invalide."}, status=400)

    except Exception as e:
        # 🚨 Gestion des erreurs inattendues
        print("Erreur inattendue:", e)
        return JsonResponse({"error": "Une erreur interne est survenue."}, status=500)


# Tableau de bord côté admin
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_stats(request):
    # Statistiques globales
    total_utilisateurs = Utilisateurs.objects.count()
    total_commandes = Commande.objects.count()
    total_produits = Produits.objects.count()
    total_fichiers = Fichier.objects.count()
    total_revenu = Commande.objects.aggregate(total=Sum('montant_total'))['total'] or 0

    # Commandes par statut
    commandes_par_statut = (
        Commande.objects
        .values('statut')
        .annotate(count=Count('id'))
        .order_by('statut')
    )

    # ✅ Commandes par mois (6 derniers mois)
    commandes_par_mois = (
        Commande.objects
        .annotate(mois=TruncMonth('date_commande'))
        .values('mois')
        .annotate(nombre=Count('id'))
        .order_by('mois')
    )

    # Dernières commandes
    dernieres_commandes = (
        Commande.objects
        .select_related('utilisateur')
        .order_by('-date_commande')[:5]
        .values(
            'id',
            'utilisateur__nom',
            'utilisateur__prenom',
            'statut',
            'montant_total',
            'date_commande'
        )
    )

    # Utilisateurs récents
    utilisateurs_recents = (
        Utilisateurs.objects
        .order_by('-date_inscription')[:5]
        .values('nom', 'prenom', 'email', 'date_inscription')
    )

    return Response({
        "totaux": {
            "utilisateurs": total_utilisateurs,
            "commandes": total_commandes,
            "produits": total_produits,
            "fichiers": total_fichiers,
            "revenu": total_revenu
        },
        "commandes_par_statut": list(commandes_par_statut),
        "commandes_par_mois": list(commandes_par_mois),
        "dernieres_commandes": list(dernieres_commandes),
        "utilisateurs_recents": list(utilisateurs_recents)
    })


# Changé le status de la commande@api_view(['POST'])
@csrf_exempt
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def changer_statut_commande(request, commande_id):
    """
    Mettre à jour le statut d'une commande.
    L'email sera envoyé automatiquement selon ta logique existante.
    """
    commande = get_object_or_404(Commande, id=commande_id)
    nouveau_statut = request.data.get('statut')

    statuts_valides = [
        'EN_ATTENTE',
        'RECU',
        'EN_COURS_IMPRESSION',
        'TERMINE',
        'EN_COURS_LIVRAISON',
        'LIVREE'
    ]

    if nouveau_statut not in statuts_valides:
        return Response({"error": "Statut invalide"}, status=400)

    commande.statut = nouveau_statut
    commande.save()  # ton trigger d'envoi d'email existant s'exécutera ici si prévu

    return Response({
        "message": f"Statut changé en {commande.get_statut_display()}",
        "commande": {
            "id": commande.id,
            "statut": commande.statut
        }
    })

# Recherche des produits
@api_view(['GET'])
@permission_classes([AllowAny])
def search_products(request):
    query = request.GET.get('search', '').strip()
    results = []

    if query:
        # Recherche dans name, description, categorie
        produits_name = Produits.objects.filter(name__icontains=query)
        produits_description = Produits.objects.filter(description__icontains=query)
        produits_categorie = Produits.objects.filter(categorie__icontains=query)

        # On peut créer des "tags" pour savoir d'où vient la correspondance
        for p in produits_name:
            results.append({**ProduitsSerializer(p).data, "match": "name"})
        for p in produits_description:
            results.append({**ProduitsSerializer(p).data, "match": "description"})
        for p in produits_categorie:
            results.append({**ProduitsSerializer(p).data, "match": "categorie"})

        # Supprimer les doublons (même id)
        seen_ids = set()
        filtered_results = []
        for item in results:
            if item["id"] not in seen_ids:
                filtered_results.append(item)
                seen_ids.add(item["id"])
        results = filtered_results

    serializer = ProduitsSerializer(results[:5], many=False)  # max 5 suggestions
    return Response(results)


# Connexion avec compte google@api_view(['POST'])
@api_view(['POST'])
@permission_classes([AllowAny])  # ✅ Important : tout le monde peut accéder
def google_login(request):
    email = request.data.get('email')
    nom = request.data.get('nom', 'Utilisateur')
    prenom = request.data.get('prenom', '')
    profil_picture = request.data.get('profil') 

    if not email:
        return Response({"error": "Email manquant"}, status=400)

    user, created = Utilisateurs.objects.get_or_create(
        email=email,
        defaults={
            "nom": nom,
            "prenom": prenom,
            "google_avatar_url": profil_picture   # Stocker uniquement l'URL
        }
    )

    # Mettre à jour l'URL Google si l'utilisateur existe
    if not created and profil_picture:
        user.google_avatar_url = profil_picture
        user.save()

    refresh = RefreshToken.for_user(user)

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "email": user.email,
            "nom": user.nom,
            "prenom": user.prenom,
            "role": user.role,
            "profils": user.google_avatar_url  # ⭐ Retourner directement l'URL Google
        }
    })



# Chat bot
# =========================================================
# 🔹 Chatbot Print.mg — Version Élégante Française
# =========================================================


# =========================================================
# 🔹 Contexte général Print.mg
# =========================================================
CONTEXT = """
Print.mg est votre plateforme d'impression de confiance à Madagascar 🖨️.
Nous spécialisons dans l'impression de qualité pour :
- Livres, documents et rapports
- Supports marketing et publicitaires
- Brochures, flyers et affiches
- Cartes de visite et supports professionnels

Informations importantes :
• Livraison : 5 000 Ar (gratuite dès 200 000 Ar d'achat) 🚚
• Formats : A3 (1 000 Ar), A4 (500 Ar), A5 (300 Ar)
• Reliures : Spirale (2 000 Ar), Perfect binding (3 000 Ar)
• Paiement : Mvola ou à la livraison
"""

# =========================================================
# 🔹 Réponses automatiques ÉLÉGANTES
# =========================================================
AUTOMATIC_ANSWERS = {
    "bonjour": "✨ Bonjour ! Je suis ravi de vous accueillir sur Print.mg 😊\nComment puis-je vous accompagner aujourd'hui ?",
    "salut": "👋 Salut ! Chez Print.mg, nous sommes à votre service.\nQue souhaitez-vous savoir ?",
    "coucou": "😀 Coucou ! Bienvenue sur Print.mg, votre expert en impression.\nComment puis-vous aider votre projet ?",
    "bonsoir": "🌙 Bonsoir ! Print.mg vous souhaite une excellente soirée.\nEn quoi puis-je vous être utile ?",
    "merci": "😊 C'est un plaisir de vous aider ! Souhaitez-vous découvrir nos produits ou passer commande ?",
    "merci beaucoup": "🙏 Je vous en prie ! Merci à vous pour votre confiance en Print.mg.\nExcellente journée à vous !",
    "ok": "☺️ Parfait ! N'hésitez pas si d'autres questions surgissent,\nje reste à votre disposition.",
    "au revoir": "👋 Au revoir ! Merci d'avoir choisi Print.mg.\nÀ très bientôt pour vos projets d'impression !",
    "bye": "👋 À bientôt ! Merci pour votre visite sur Print.mg 🌟",
    "commande": (
        "🎉 **Voici comment passer commande sur Print.mg** 🖨️ :\n\n"
        "1️⃣ **Connexion** : Accédez à votre espace client\n"
        "2️⃣ **Téléversement** : Importez vos fichiers à imprimer\n"
        "3️⃣ **Personnalisation** : Choisissez format, finition, quantité\n"
        "4️⃣ **Devis** : Visualisez le prix instantanément\n"
        "5️⃣ **Livraison** : Sélectionnez votre mode de réception\n"
        "6️⃣ **Paiement** : Finalisez par Mvola ou à la livraison\n\n"
        "Prêt à donner vie à votre projet ? ✨"
    ),
    "livraison": (
        "🚚 **Informations de livraison Print.mg** :\n\n"
        "• **Zone Antananarivo** : 5 000 Ar\n"
        "• **Gratuite** dès 200 000 Ar d'achat ✅\n"
        "• **Suivi** : Accompagnement de votre commande\n"
        "• **Professionnalisme** : Livraison soignée et sécurisée"
    ),
}

BOOK_PRICES_MESSAGE = """📖 **Tarifs détaillés pour les livres** :

🖼️ **Formats** :
• A3 : 1 000 Ar
• A4 : 500 Ar  
• A5 : 300 Ar
• Personnalisé : 200 Ar
• Large format : 5 000 Ar

📚 **Reliures** :
• Spirale : 2 000 Ar
• Perfect binding : 3 000 Ar
• Agrafée : 1 000 Ar
• Couverture rigide : 5 000 Ar
• Dos caré Cousu : 1 000 Ar

🛡️ **Couvertures** :
• Papier photo : 3 000 Ar
• Papier Simple : 1 000 Ar
• Papier couché Mat : 4 000 Ar
• Papier couché Brillant : 4 500 Ar
• Papier Création Texturé : 6 000 Ar

🚚 **Livraison** : 5 000 Ar (Antananarivo)
"""

# =========================================================
# 🔹 Mots-clés
# =========================================================
COMMAND_KEYWORDS = ["commande", "acheter", "achat", "passer commande", "commander"]
PRICE_KEYWORDS = ["prix", "combien", "tarif", "coût", "montant", "argent"]
PRODUCT_KEYWORDS = ["produit", "offre", "impression", "service", "imprimer"]
DELIVERY_KEYWORDS = ["livraison", "livrer", "expédition", "délai", "livreur"]
POLITE_KEYWORDS = ["bonjour", "salut", "bonsoir", "coucou", "merci", "ok", "bye", "au revoir", "merci beaucoup"]
SUIVI_KEYWORDS = ["suivi", "suivre", "statut", "où est", "état", "tracking", "numéro de commande"]

# =========================================================
# 🔹 Modèle Français Élégant - REMPLACE MISTRAL
# =========================================================
def get_hf_token():
    """Récupère le token Hugging Face de manière sécurisée"""
    token = config("HF_TOKEN", default="")
    
    if not token:
        print("⚠️  HF_TOKEN non configuré dans le fichier .env")
        return ""
    
    return token

def ask_elegant_french_ai(question: str):
    """Appel à un modèle français élégant sur Hugging Face"""
    
    # 🔥 MODÈLES FRANÇAIS RECOMMANDÉS (choisissez-en un)
    API_URL = "https://api-inference.huggingface.co/models/asi/gpt-fr-cased-base"
    # API_URL = "https://api-inference.huggingface.co/models/babelscape/rebel-large-french"
    
    HF_TOKEN = get_hf_token()
    
    if not HF_TOKEN:
        return get_elegant_fallback(question)
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 🎯 PROMPT ÉLÉGANT ET POLI
    prompt = f"""
    [ROLE] Vous êtes l'assistant virtuel de Print.mg, plateforme d'impression malgache.
    
    [STYLE] 
    - Ton : chaleureux, professionnel et élégant
    - Langage : français poli et courtois
    - Structure : phrases fluides et naturelles
    - Emojis : utilisés avec modération (1-2 max)
    - Longueur : 2-4 phrases maximum
    
    [CONTEXTE PRINT.MG]
    Print.mg est votre partenaire d'impression à Madagascar.
    Services : impression de livres, documents, supports marketing.
    Livraison : 5 000 Ar Antananarivo (gratuite >200 000 Ar).
    Prix livre : A4=500Ar, A3=1000Ar, A5=300Ar.
    Reliure : Spirale=2000Ar, Perfect binding=3000Ar.
    
    [QUESTION] {question}
    
    [RÉPONSE ÉLÉGANTE]
    """
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.7,
            "do_sample": True,
            "top_p": 0.9,
            "repetition_penalty": 1.2
        }
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        
        # Gestion des erreurs HTTP
        if response.status_code == 401:
            return "🔐 Erreur d'authentification. Token Hugging Face invalide."
        elif response.status_code == 503:
            return get_elegant_fallback(question)
        elif response.status_code != 200:
            return get_elegant_fallback(question)
        
        data = response.json()

        if isinstance(data, dict) and data.get("error"):
            return get_elegant_fallback(question)

        if isinstance(data, list) and len(data) > 0:
            text = data[0].get("generated_text", "")
            
            # Extraire la réponse après le marqueur
            if "RÉPONSE ÉLÉGANTE]" in text:
                answer = text.split("RÉPONSE ÉLÉGANTE]")[-1].strip()
            else:
                answer = text.strip()
            
            # Nettoyer la réponse
            answer = _clean_response(answer)
            
            # Valider que c'est une bonne réponse française
            if answer and _is_good_french_response(answer):
                return answer
        
        return get_elegant_fallback(question)
        
    except Exception as e:
        print("Erreur API French AI:", e)
        return get_elegant_fallback(question)

def _clean_response(text: str) -> str:
    """Nettoyer la réponse pour plus d'élégance"""
    # Supprimer les répétitions de prompt
    text = text.split("[QUESTION]")[0].strip()
    text = text.split("[SYSTÈME]")[0].strip()
    
    # Capitaliser la première lettre
    if text and len(text) > 0:
        text = text[0].upper() + text[1:]
    
    return text

def _is_good_french_response(text: str) -> bool:
    """Vérifier que la réponse est de bonne qualité française"""
    if len(text.strip()) < 10:
        return False
    
    # Vérifier la structure de phrase
    has_punctuation = any(punc in text for punc in ['.', '!', '?', '\n'])
    has_french_words = any(word in text.lower() for word in ['le', 'la', 'les', 'de', 'des', 'notre', 'vos'])
    
    return has_punctuation and (has_french_words or len(text.split()) > 5)

# =========================================================
# 🔹 Fonctions utilitaires AMÉLIORÉES
# =========================================================
def detect_intent(question: str):
    q = question.lower()
    for key in COMMAND_KEYWORDS:
        if key in q: return "commande"
    for key in PRICE_KEYWORDS:
        if key in q: return "prix"
    for key in PRODUCT_KEYWORDS:
        if key in q: return "produit"
    for key in DELIVERY_KEYWORDS:
        if key in q: return "livraison"
    for key in SUIVI_KEYWORDS:
        if key in q: return "suivi"
    for key in POLITE_KEYWORDS:
        if key in q: return key
    return None

def get_all_products_with_prices():
    produits = Produits.objects.all()
    if not produits.exists():
        return "📦 **Nos services Print.mg** :\n\n• Impression de livres et documents\n• Supports marketing et publicitaires\n• Brochures et flyers professionnels\n\n🚚 Livraison : 5 000 Ar (gratuite >200 000 Ar)"
    
    message = "💰 **Nos produits et tarifs** :\n\n"
    for idx, p in enumerate(produits, start=1):
        message += f"• **{p.name}** : {p.prix:.0f} Ar\n"
    
    message += "\n🚚 **Livraison** : 5 000 Ar pour Antananarivo"
    message += "\n" + BOOK_PRICES_MESSAGE
    return message

def get_price_for_product(question):
    produits = Produits.objects.all()
    q = question.lower()
    for p in produits:
        if p.name.lower() in q:
            return f"💵 **{p.name}** est à **{p.prix:.0f} Ar**.\n\nSouhaitez-vous des informations sur la commande ? 😊"
    return None

def get_elegant_fallback(question: str):
    """Fallback avec des réponses élégantes pré-définies"""
    q = question.lower()
    
    # 🔥 RÉPONSES ÉLÉGANTES CONTEXTUELLES
    if "print.mg" in q or "printmg" in q or "c'est quoi print" in q:
        return (
            "✨ **Print.mg** est votre partenaire d'impression de confiance à Madagascar !\n\n"
            "Nous nous spécialisons dans :\n"
            "• 📚 Livres et documents de qualité\n"
            "• 🎨 Supports marketing percutants\n"
            "• 📄 Brochures et flyers professionnels\n\n"
            "Avec livraison sur Antananarivo et un service personnalisé 🚚"
        )
    elif "qui êtes" in q or "qui es" in q or "tu es qui" in q:
        return (
            "👋 Je suis l'assistant virtuel de Print.mg !\n\n"
            "Je suis ici pour vous accompagner dans vos projets d'impression, "
            "vous renseigner sur nos tarifs et vous guider dans vos commandes.\n\n"
            "Comment puis-je vous être utile aujourd'hui ? 😊"
        )
    elif "service" in q or "offre" in q or "propos" in q:
        return (
            "🎯 **Print.mg vous propose** :\n\n"
            "• Impression de livres et documents\n"
            "• Création de supports marketing\n"
            "• Brochures, flyers et affiches\n"
            "• Livraison professionnelle\n\n"
            "Quel projet souhaitez-vous concrétiser ?"
        )
    elif any(word in q for word in PRICE_KEYWORDS):
        return (
            "💰 **Nos tarifs transparents** :\n\n"
            "Voici nos principaux prix pour vous orienter :\n\n"
            "📄 **Formats Papier**\n"
            "• A3 : 1 000 Ar\n"
            "• A4 : 500 Ar\n"
            "• A5 : 300 Ar\n\n"
            "📚 **Reliures**\n"
            "• Spirale : 2 000 Ar\n"
            "• Perfect binding : 3 000 Ar\n\n"
            "🚚 **Livraison** : 5 000 Ar (gratuite >200 000 Ar)\n\n"
            "Souhaitez-vous un devis personnalisé ? 😊"
        )
    elif any(word in q for word in COMMAND_KEYWORDS):
        return AUTOMATIC_ANSWERS["commande"]
    elif any(word in q for word in DELIVERY_KEYWORDS):
        return AUTOMATIC_ANSWERS["livraison"]
    
    # Réponse générique élégante
    return (
        "🤗 Je suis ravi de vous aider chez Print.mg !\n\n"
        "Je peux vous renseigner sur :\n"
        "• 📋 Le processus de commande\n"
        "• 💰 Nos tarifs compétitifs\n"
        "• 📦 Nos produits et services\n"
        "• 🚚 Les options de livraison\n\n"
        "Que souhaitez-vous savoir ? ✨"
    )

# =========================================================
# 🔹 FONCTIONS MANQUANTES - À AJOUTER
# =========================================================

def is_complex_question(question: str) -> bool:
    """Détecte si la question nécessite une réponse complexe (IA)"""
    q = question.lower()
    
    # Indicateurs de questions complexes
    complex_indicators = [
        "différence entre", "quel est le meilleur", "conseillez", "recommandez",
        "problème", "erreur", "comment optimiser", "quelle qualité", 
        "délai", "urgence", "hors d'antananarivo", "en dehors de",
        "spécial", "personnalisé", "sur mesure", "option", "alternative",
        "résolution", "marges", "relecture", "correction", "horaires",
        "calcul", "estimation", "combien coûterait", "quel serait le prix",
        "100 pages", "200 pages", "50 pages", "couverture rigide", "reliure spirale"
    ]
    
    # Questions avec calcul de prix personnalisé
    has_custom_calculation = (
        any(page in q for page in ["100 pages", "200 pages", "50 pages", "pages"]) and 
        any(format_word in q for format_word in ["a4", "a3", "a5"]) and
        any(binding in q for binding in ["spirale", "perfect", "reliure"])
    )
    
    # Questions longues (>8 mots) souvent complexes
    is_long_question = len(question.split()) > 8
    
    # Questions avec plusieurs aspects
    has_multiple_aspects = any([
        " et " in q and ("prix" in q or "coût" in q or "délai" in q),
        " mais " in q,
        " cependant " in q,
        " par contre " in q
    ])
    
    return (any(indicator in q for indicator in complex_indicators) 
            or is_long_question 
            or has_multiple_aspects
            or has_custom_calculation)

def get_detailed_fallback(question: str):
    """Fallback ultra-détaillé pour chaque type de question complexe"""
    q = question.lower()
    
    # 🔥 RÉPONSES SPÉCIFIQUES POUR CHAQUE QUESTION COMPLEXE
    
    # 1. Calcul de prix pour livre personnalisé
    if any(word in q for word in ["100 pages", "200 pages", "50 pages", "pages"]) and "livre" in q:
        if "a4" in q and "spirale" in q:
            return ("📚 Pour un livre de 100 pages A4 avec reliure spirale :\n\n"
                   "• 100 pages A4 : 50 000 Ar (500 Ar/page)\n"
                   "• Reliure spirale : 2 000 Ar\n"
                   "• Couverture rigide : 3 000 Ar\n"
                   "• **Total estimé : 55 000 Ar**\n\n"
                   "Délai : 3-5 jours ouvrés. Souhaitez-vous un devis exact ? 😊")
    
    # 2. Différence entre reliures
    if "différence" in q and ("spirale" in q or "perfect" in q):
        return ("📖 **Différence entre reliures** :\n\n"
               "• **Spirale** (2000 Ar) : Pratique, pages plates, idéale pour documents fréquemment utilisés\n"
               "• **Perfect Binding** (3000 Ar) : Aspect professionnel, dos carré, parfaite pour mémoires et rapports\n"
               "• **Agrafé** (1000 Ar) : Économique, pour documents de moins de 50 pages\n\n"
               "Laquelle correspond le mieux à votre projet ? ✨")
    
    # 3. Problème qualité image
    if "basse résolution" in q or "qualité image" in q or "résolution" in q:
        return ("🖼️ **Qualité d'impression des images** :\n\n"
               "Pour une impression optimale, nous recommandons :\n"
               "• **300 DPI** minimum pour les images\n"
               "• Formats : PDF, JPG, PNG haute qualité\n"
               "• Taille des images : adaptée au format final\n\n"
               "Nous pouvons vérifier vos fichiers gratuitement avant impression ! 📄")
    
    # 4. Conseil pour restaurant
    if "restaurant" in q and "flyer" in q:
        return ("🍽️ **Flyers pour restaurant - Nos conseils** :\n\n"
               "• **Format A5** : Parfait pour la distribution\n"
               "• **Papier brillant** : Met en valeur les photos de plats\n"
               "• **500 flyers** : 25 000 Ar (50 Ar/unité)\n"
               "• **Conseil** : Ajoutez un coupon de réduction !\n\n"
               "Prêt à impressionner vos clients ? 🎯")
    
    # 5. Marges document
    if "marges" in q or "marge" in q:
        return ("📐 **Recommandations marges** :\n\n"
               "• **Minimum conseillé** : 1.5 cm sur tous les bords\n"
               "• **Idéal** : 2 cm pour une impression professionnelle\n"
               "• **Importante** : Vérifiez le fond perdu si vos éléments touchent les bords\n\n"
               "Vos marges de 2cm sont parfaites ! ✅")
    
    
    # 7. Services relecture
    if "relecture" in q or "correction" in q:
        return ("✏️ **Services de relecture** :\n\n"
               "Nous nous concentrons sur l'impression de qualité.\n"
               "**Conseil** : Faites relire vos documents avant impression par :\n"
               "• Votre entourage\n"
               "• Des services de relecture en ligne\n"
               "• Des professionnels locaux\n\n"
               "Nous imprimons ce que vous nous fournissez ! 📝")
    
    # 8. Horaires
    if "horaires" in q or "heure" in q or "ouvrir" in q:
        return ("🕐 **Nos horaires Print.mg** :\n\n"
               "• **Lundi - Vendredi** : 8h00 - 17h00\n"
               "• **Samedi** : 8h00 - 12h00\n"
               "• **Dimanche** : Fermé\n"
               "• **Dépôt fichiers** : Possible aux horaires d'ouverture\n\n"
               "À bientôt dans notre atelier ! 🏢")
    
    # Réponse par défaut élégante
    return get_elegant_fallback(question)

def get_simple_response(question: str):
    """Gère TOUTES les réponses simples sans IA"""
    q = question.lower()
    
    # 0. 🔥 EXCLURE LES QUESTIONS COMPLEXES EN PREMIER
    if is_complex_question(question):
        return None
    
    # 1. Politesse
    intent = detect_intent(q)
    if intent in POLITE_KEYWORDS:
        remaining = q.replace(intent, "").strip()
        if not remaining:
            return AUTOMATIC_ANSWERS[intent]
        # Si reste après politesse, vérifier si c'est complexe
        if is_complex_question(remaining):
            return None
    
    # 2. 🔥 DÉTECTION SPÉCIFIQUE DES CALCULS DE PRIX COMPLEXES
    if any(word in q for word in ["100 pages", "200 pages", "50 pages", "pages"]) and "livre" in q:
        if "a4" in q and "spirale" in q:
            return None  # Laisser get_detailed_fallback gérer
    
    # 3. Produits spécifiques
    specific_product = detect_specific_products(q)
    if specific_product:
        return specific_product
    
    # 4. Prix spécifiques
    product_price = get_price_for_product(q)
    if product_price:
        return product_price
    
    # 5. Commandes & livraison
    if any(word in q for word in COMMAND_KEYWORDS):
        return AUTOMATIC_ANSWERS["commande"]
    
    if any(word in q for word in DELIVERY_KEYWORDS):
        return AUTOMATIC_ANSWERS["livraison"]
    
    # 6. Présentation Print.mg
    if "print.mg" in q or "printmg" in q or "c'est quoi print" in q:
        return get_elegant_fallback(q)
    
    # 7. Produits généraux
    if any(word in q for word in PRODUCT_KEYWORDS):
        if not has_specific_product_mention(q):
            produits = Produits.objects.all()
            if produits.exists():
                noms = ", ".join([p.name for p in produits])
                return f"📦 **Nos produits Print.mg** : {noms}.\n\n{BOOK_PRICES_MESSAGE}"
    
    # 8. Prix généraux
    if any(word in q for word in PRICE_KEYWORDS):
        return get_all_products_with_prices()
    
    return None
# =========================================================
# 🔹 Vue principale Chatbot - VERSION CORRIGÉE
# =========================================================
@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot(request):
    question = request.data.get("question", "").strip()
    
    if not question:
        return Response({"answer": "🤗 Bonjour ! Une question sur Print.mg ? Je suis là pour vous aider 😊"})

    q = question.lower()

    # 🔥 NOUVEAU : SUIVI DE COMMANDE (très simple)
    if any(word in q for word in ["suivi", "statut", "où est", "état", "tracking"]):
        suivi_response = get_suivi_commande_response()
        return Response({"answer": suivi_response})

    # 1️⃣ RECHERCHE DE RÉPONSE SIMPLE (PRIORITÉ ABSOLUE)
    simple_response = get_simple_response(q)
    if simple_response:
        return Response({"answer": simple_response})

    # 2️⃣ DÉTECTION QUESTIONS COMPLEXES
    if is_complex_question(question):
        print(f"🔍 Question complexe détectée: {question}")
        
        # Essayer d'abord le fallback détaillé
        detailed_response = get_detailed_fallback(question)
        if detailed_response != get_elegant_fallback(question):
            return Response({"answer": detailed_response})
        
        # Sinon utiliser le modèle IA
        answer = ask_elegant_french_ai(question)
        return Response({"answer": answer})

    # 3️⃣ FALLBACK GÉNÉRAL
    return Response({"answer": get_elegant_fallback(question)})

# =========================================================
# 🔹 Nouvelles fonctions de détection spécifique
# =========================================================

def detect_specific_products(question: str):
    """Détecte les mentions de produits spécifiques dans la question"""
    q = question.lower()
    
    # Dictionnaire des produits spécifiques et leurs réponses
    specific_products = {
        "flyer": {
            "keywords": ["flyer", "flyers", "tract", "tracts"],
            "response": "🎯 **Flyers Print.mg** :\n\n• **Prix** : 50 Ar l'unité\n• **Format standard** : A5/A6\n• **Papier** : Brillant ou mat\n• **Quantité** : À partir de 100 unités\n\nParfait pour vos événements et promotions ! 🚀"
        },
        "carte de visite": {
            "keywords": ["carte de visite", "cart de visite", "carte visite"],
            "response": "📇 **Cartes de visite Print.mg** :\n\n• **Prix** : 100 Ar l'unité\n• **Format** : 8.5 x 5.5 cm\n• **Finitions** : Brillant, mat, vernis sélectif\n• **Recto/verso** : Disponible\n\nProfessionnalisez votre image ! ✨"
        },
        "poster": {
            "keywords": ["poster", "affiche", "affiches"],
            "response": "🖼️ **Posters & Affiches Print.mg** :\n\n• **Prix** : 500 Ar l'unité\n• **Formats** : A4, A3, A2, sur mesure\n• **Papier** : Photo qualité premium\n• **Encadrement** : Option disponible\n\nIdéal pour décoration et promotion ! 🎨"
        },
        "livre": {
            "keywords": ["livre", "livres", "brochure", "brochures"],
            "response": "📚 **Livres & Brochures Print.mg** :\n\n" + BOOK_PRICES_MESSAGE + "\n\nNous personnalisons selon votre projet ! 😊"
        },
        "document": {
            "keywords": ["document", "documents", "rapport", "mémoire"],
            "response": "📄 **Documents professionnels Print.mg** :\n\n• **Impression noir & blanc** : 20 Ar/page\n• **Impression couleur** : 50 Ar/page\n• **Reliure** : Spirale, agrafée, reliure cousue\n• **Options** : Couverture rigide, personnalisation\n\nParfait pour rapports et mémoires ! 📊"
        }
    }
    
    for product_name, product_info in specific_products.items():
        for keyword in product_info["keywords"]:
            if keyword in q:
                return product_info["response"]
    
    return None

def get_specific_price_response(question: str):
    """Donne une réponse de prix spécifique plutôt que la liste générale"""
    q = question.lower()
    
    # Vérifier d'abord les produits spécifiques
    specific_response = detect_specific_products(q)
    if specific_response:
        return specific_response
    
    # Vérifier les produits de la base de données
    product_price = get_price_for_product(q)
    if product_price:
        return product_price
    
    return None

def has_specific_product_mention(question: str):
    """Vérifie si la question mentionne un produit spécifique"""
    q = question.lower()
    
    specific_mentions = [
        "flyer", "carte de visite", "poster", "affiche", "livre", 
        "brochure", "document", "rapport", "mémoire", "catalogue"
    ]
    
    return any(mention in q for mention in specific_mentions)

# =========================================================
# 🔹 Mise à jour de la fonction get_price_for_product
# =========================================================
def get_price_for_product(question):
    """Version améliorée avec réponses plus élégantes"""
    produits = Produits.objects.all()
    q = question.lower()
    
    for p in produits:
        if p.name.lower() in q:
            return (
                f"💵 **{p.name}** - **{p.prix:.0f} Ar**\n\n"
                f"Ce tarif comprend une impression de qualité professionnelle.\n"
                f"Souhaitez-vous des détails sur les options ou passer commande ? 😊"
            )
    return None

def get_suivi_commande_response():
    """Explique le processus de suivi de Print.mg"""
    return (
        "📊 **Suivi de commande Print.mg**\n\n"
        "**Notre processus de suivi :**\n\n"
        "• 📧 **Emails automatiques** :\n"
        "  - Confirmation de commande\n"
        "  - Commande en production  \n"
        "  - Commande prête\n"
        "  - Livraison en cours\n\n"
        "• 📞 **Appels téléphoniques** :\n"
        "  - 3 appels minimum jusqu'à livraison\n"
        "  - Confirmation et suivi\n"
        "  - Coordination livraison\n\n"
        "• 🔄 **Mise à jour automatique** :\n"
        "  - Statuts mis à jour en temps réel\n"
        "  - Pas besoin de chercher l'info\n"
        "  - On vous tient informé !\n\n"
        "**Détendez-vous, on s'occupe de tout !** 🎉\n\n"
        "📞 Contactez-nous si pas de nouvelles sous 24h !"
    )

# Dans votre views.py Django

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sent_notifications(request):
    try:
        # Trouver le profil Utilisateurs correspondant à l'User Django
        # Cela dépend de comment vous avez lié les deux modèles
        
        # Option 1: Si vous avez un OneToOneField
        # utilisateur = Utilisateurs.objects.get(user=request.user)
        
        # Option 2: Si vous utilisez le même email
        utilisateur = Utilisateurs.objects.filter(email=request.user.email).first()
        
        if not utilisateur:
            return Response({'error': 'Profil utilisateur non trouvé'}, status=404)
        
        # Maintenant filtrez les notifications
        sent_notifications = Notification.objects.filter(
            sender=utilisateur,
            is_deleted=False
        ).order_by('-created_at')
        
        # Pour éviter les doublons, vous pouvez exclure les notifications
        # où l'utilisateur est à la fois sender et user (copies)
        sent_notifications = sent_notifications.exclude(user=utilisateur)
        
        serializer = NotificationSerializer(sent_notifications, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return Response({'error': str(e)}, status=500)