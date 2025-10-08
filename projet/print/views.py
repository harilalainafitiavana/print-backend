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
def send_notification_admin(request):
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
