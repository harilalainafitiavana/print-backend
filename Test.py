if __name__ == "__main__":
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

    print("⏳ Chargement du modèle BlenderBot 400M...")

    model_name = "facebook/blenderbot-400M-distill"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    chatbot = pipeline("text2text-generation", model=model, tokenizer=tokenizer)

    # Instructions principales pour le bot
    context_instruction = (
        "Tu es un assistant pour Print.mg, une plateforme d'impression en ligne à Madagascar. "
        "Réponds uniquement aux questions concernant Print.mg. "
        "Si l'utilisateur dit bonjour, merci ou autre salutation, réponds poliment. "
        "Pour toute demande de commande, prix ou produit, réponds selon le contexte Print.mg."
    )

    # Informations détaillées que le bot pourra utiliser si besoin
    printmg_context = (
        "Print.mg propose : flyers, cartes de visite, affiches, posters, livres reliés.\n"
        "Prix : Flyers 50 Ar/unité, Cartes 100 Ar/unité, Posters 500 Ar/unité.\n"
        "Livraison gratuite pour les commandes supérieures à 10 000 Ar.\n"
        "Étapes pour passer une commande :\n"
        "1. Choisissez un produit sur la page 'Produits'.\n"
        "2. Personnalisez les options (format, quantité, finition).\n"
        "3. Cliquez sur 'Ajouter au panier'.\n"
        "4. Allez dans votre panier et cliquez sur 'Commander'.\n"
        "5. Remplissez vos informations et validez.\n"
        "6. Paiement à la livraison ou par mobile money."
    )

    print("\n🤖 Assistant Print.mg prêt ! Tape 'quit' pour quitter.\n")

    while True:
        user_input = input("Vous: ").strip()
        if user_input.lower() in ["quit", "exit"]:
            print("👋 Au revoir !")
            break

        # Construire un prompt court pour éviter l'erreur de longueur
        prompt = (
            f"{context_instruction}\n"
            f"Contexte détaillé: {printmg_context}\n"
            f"Utilisateur: {user_input}\n"
            f"Assistant:"
        )

        try:
            response = chatbot(
                prompt,
                max_new_tokens=150,
                temperature=0.8,
                top_p=0.9,
                do_sample=True
            )
            print("Bot:", response[0]["generated_text"])
        except Exception as e:
            print("Oups, une erreur est survenue :", e)
