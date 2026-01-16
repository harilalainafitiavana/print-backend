# validators.py - VERSION COMPLÈTE
import os
from PIL import Image, ImageFile
from io import BytesIO
from decimal import Decimal
from django.core.exceptions import ValidationError

# Pour éviter les erreurs avec les images tronquées
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ESSAYER D'IMPORTER pypdf AVEC PLUS DE RIGUEUR
PDF2_AVAILABLE = False
PyPDF2 = None

try:
    import pypdf
    PyPDF2 = pypdf  # Alias pour la compatibilité
    PDF2_AVAILABLE = True
    print(f"✅ pypdf version {pypdf.__version__} disponible")
except ImportError:
    print("❌ pypdf NON DISPONIBLE - La validation PDF ne fonctionnera pas !")
    print("   Exécutez: pip install pypdf")

# Formats acceptés
FORMATS_ACCEPTES = {
    'pdf': ['application/pdf'],
    'image': ['image/jpeg', 'image/jpg', 'image/png']
}

# Dimensions standards (en mm)
FORMAT_DIMENSIONS = {
    'A3': (297, 420),
    'A4': (210, 297),
    'A5': (148, 210),
}

# Tolérance en mm (pour le format personnalisé)
TOLERANCE_MM = 2

# ------------------------------------------------------------
# FONCTIONS MANQUANTES QUE VOUS DEVEZ AJOUTER :
# ------------------------------------------------------------

def get_file_info(file_obj):
    """Extrait les informations du fichier"""
    file_info = {
        'name': file_obj.name,
        'size': file_obj.size,
        'content_type': file_obj.content_type,
        'extension': os.path.splitext(file_obj.name)[1].lower()
    }
    return file_info

def validate_pdf_dimensions(file_obj, expected_width, expected_height):
    """Vérifie les dimensions d'un PDF"""
    if not PDF2_AVAILABLE:
        return True, {"warning": "PyPDF2 non disponible, validation des dimensions PDF ignorée"}
    
    try:
        # Lire le PDF
        pdf_reader = PyPDF2.PdfReader(file_obj)
        
        if len(pdf_reader.pages) == 0:
            return False, "PDF vide"
        
        # Prendre la première page comme référence
        page = pdf_reader.pages[0]
        media_box = page.mediabox
        
        # Les dimensions sont en points (1 point = 1/72 inch)
        # Convertir en mm: 1 point = 0.352778 mm
        width_pt = float(media_box.width)
        height_pt = float(media_box.height)
        
        width_mm = width_pt * 0.352778
        height_mm = height_pt * 0.352778
        
        # Réorganiser pour s'assurer que width < height (portrait)
        if width_mm > height_mm:
            width_mm, height_mm = height_mm, width_mm
        
        # Vérifier les dimensions
        width_ok = abs(width_mm - expected_width) <= TOLERANCE_MM
        height_ok = abs(height_mm - expected_height) <= TOLERANCE_MM
        
        return width_ok and height_ok, {
            'found': (width_mm, height_mm),
            'expected': (expected_width, expected_height)
        }
        
    except Exception as e:
        return False, f"Erreur lecture PDF: {str(e)}"

def validate_image_dimensions(file_obj, expected_width, expected_height):
    """Vérifie les dimensions d'une image"""
    try:
        # Ouvrir l'image
        image = Image.open(file_obj)
        width_px, height_px = image.size
        
        # Obtenir la résolution DPI
        dpi = image.info.get('dpi', (72, 72))
        dpi_horizontal = dpi[0]
        
        # Convertir les pixels en mm
        # 1 inch = 25.4 mm, donc mm = (pixels * 25.4) / DPI
        if dpi_horizontal > 0:
            width_mm = (width_px * 25.4) / dpi_horizontal
            height_mm = (height_px * 25.4) / dpi_horizontal
        else:
            # DPI par défaut si non spécifié
            width_mm = (width_px * 25.4) / 72
            height_mm = (height_px * 25.4) / 72
        
        # Réorganiser pour portrait
        if width_mm > height_mm:
            width_mm, height_mm = height_mm, width_mm
        
        # Vérifier les dimensions
        width_ok = abs(width_mm - expected_width) <= TOLERANCE_MM
        height_ok = abs(height_mm - expected_height) <= TOLERANCE_MM
        
        return width_ok and height_ok, {
            'found': (width_mm, height_mm),
            'expected': (expected_width, expected_height),
            'dpi': dpi_horizontal
        }
        
    except Exception as e:
        return False, f"Erreur lecture image: {str(e)}"

def get_expected_dimensions(config):
    """Récupère les dimensions attendues basées sur la configuration"""
    if config.format_type == 'petit' and config.small_format:
        if config.small_format in FORMAT_DIMENSIONS:
            return FORMAT_DIMENSIONS[config.small_format]
    
    elif config.format_type == 'grand':
        if config.largeur and config.hauteur:
            # Convertir cm en mm (votre modèle stocke en cm)
            return (float(config.largeur) * 10, float(config.hauteur) * 10)
    
    return None

# ------------------------------------------------------------
# FONCTION PRINCIPALE (que vous avez déjà)
# ------------------------------------------------------------

def validate_file_against_config(file_obj, config):
    """Validation principale du fichier par rapport à la configuration"""
    errors = []
    warnings = []
    file_info = get_file_info(file_obj)
    
    print(f"🔍 DEBUT validation - Fichier: {file_info['name']}, Extension: {file_info['extension']}")
    print(f"🔍 Config is_book: {config.is_book}, book_pages: {config.book_pages}")
    
    # 1. Vérifier le format de fichier (TOUJOURS)
    if file_info['extension'] not in ['.pdf', '.jpg', '.jpeg', '.png']:
        errors.append(f"Format non supporté: {file_info['extension']}. Formats acceptés: .pdf, .jpg, .jpeg, .png")
    
    # 2. Vérification CRITIQUE : Pour les livres, DOIT être un PDF
    # ⭐⭐ CE BLOC EST LE PLUS IMPORTANT ⭐⭐
    if config.is_book:
        print(f"📖 LIVRE DÉTECTÉ - Vérification stricte PDF requise")
        
        # Vérification OBLIGATOIRE : format PDF pour les livres
        if file_info['extension'] != '.pdf':
            errors.append("❌ Pour les livres, seul le format PDF est accepté")
            print(f"❌ REJET: Livre avec fichier {file_info['extension']} au lieu de .pdf")
            # On retourne IMMÉDIATEMENT, pas besoin de continuer
            return {
                'is_valid': False,
                'errors': errors,
                'warnings': warnings,
                'file_info': file_info
            }
        
        # Si on arrive ici, c'est un PDF pour un livre
        print(f"✅ PDF accepté pour livre")
        
        # Vérification OBLIGATOIRE : nombre de pages
        if config.book_pages:
            file_obj.seek(0)  # Réinitialiser le pointeur
            
            if not PDF2_AVAILABLE:
                errors.append("❌ Système de validation PDF non disponible. Contactez l'administrateur.")
                print("❌ PDF2_AVAILABLE = False")
            else:
                try:
                    # Lire le PDF et compter les pages
                    pdf_reader = PyPDF2.PdfReader(file_obj)
                    actual_pages = len(pdf_reader.pages)
                    expected_pages = config.book_pages
                    
                    print(f"🔍 Pages PDF trouvées: {actual_pages}, Pages configurées: {expected_pages}")
                    
                    if actual_pages != expected_pages:
                        error_msg = f"❌ Nombre de pages incorrect. Fichier: {actual_pages} pages, Configuration: {expected_pages} pages"
                        errors.append(error_msg)
                        print(error_msg)
                    
                except Exception as e:
                    errors.append(f"❌ Impossible de lire le PDF: {str(e)}")
                    print(f"❌ Erreur lecture PDF: {e}")
    
    # 3. Vérifier la taille maximale (10MB) - UNIQUEMENT si ce n'est pas déjà rejeté
    if not errors:
        max_size_mb = 10
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_info['size'] > max_size_bytes:
            errors.append(f"Fichier trop volumineux ({file_info['size']/1024/1024:.2f}MB). Maximum: {max_size_mb}MB")
    
    # 4. Vérifier les dimensions si la configuration le permet
    expected_dimensions = get_expected_dimensions(config)
    
    if expected_dimensions and PDF2_AVAILABLE and not errors:
        expected_width, expected_height = expected_dimensions
        
        # Réinitialiser le pointeur du fichier
        file_obj.seek(0)
        
        if file_info['extension'] == '.pdf':
            is_valid, details = validate_pdf_dimensions(file_obj, expected_width, expected_height)
            if not is_valid and not isinstance(details, dict):
                errors.append(f"Dimensions PDF incorrectes. Attendu: {expected_width:.1f}x{expected_height:.1f}mm")
        
        elif file_info['extension'] in ['.jpg', '.jpeg', '.png']:
            is_valid, details = validate_image_dimensions(file_obj, expected_width, expected_height)
            if not is_valid:
                errors.append(f"Dimensions image incorrectes. Attendu: {expected_width:.1f}x{expected_height:.1f}mm")
            
            # Vérifier la résolution DPI pour les images
            if isinstance(details, dict) and 'dpi' in details and details['dpi'] < 150:
                warnings.append(f"⚠️ Résolution basse ({details['dpi']} DPI). Recommandé: 300 DPI pour une impression de qualité")
    
    # 5. Vérification recto/verso
    if config.duplex == 'recto_verso':
        if config.is_book and config.book_pages:
            # Pour un livre, nombre de pages doit être pair
            if config.book_pages % 2 != 0:
                warnings.append("⚠️ Pour l'impression recto/verso d'un livre, un nombre pair de pages est recommandé")
    
    # LOG IMPORTANT pour le débogage
    if errors:
        print(f"🚨 COMMANDE REJETÉE - Erreurs: {errors}")
    else:
        print(f"✅ FICHIER VALIDÉ - Warnings: {warnings}")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'file_info': file_info
    }