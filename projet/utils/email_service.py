import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

if not resend.api_key:
    raise Exception("❌ RESEND_API_KEY manquante")


def send_resend_email(to_email, subject, message):
    try:
        response = resend.Emails.send({
            "from": "Print.mg <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": message.replace("\n", "<br>"),
        })

        print("✅ Email envoyé via Resend:", response)
        return True

    except Exception as e:
        print("❌ Erreur Resend:", str(e))
        return False