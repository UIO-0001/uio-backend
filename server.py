# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime
import requests
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
GMAIL_USER        = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD    = os.environ.get("GMAIL_PASSWORD", "")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDENTIALS", "")

CLIENTS = {
    "uio": {
        "nom": "Assistant UIO",
        "couleur": "#7c5cfc",
        "suggestions": ["Nos services", "Nos tarifs", "Comment ca marche ?"],
        "lead_email": os.environ.get("GMAIL_USER", ""),
        "lead_sheet_id": os.environ.get("GOOGLE_SHEET_ID", ""),
        "system_prompt": (
            "Tu es l'assistant IA de UIO Automatisation, une entreprise quebecoise specialisee en chatbots IA et sites web pour les petites entreprises.\n\n"
            "MESSAGE D ACCUEIL : Quand tu recois le message [INIT], presente-toi ainsi : "
            "Bonjour ! Je suis l'assistant IA de UIO. Je peux vous aider a decouvrir nos services, obtenir une estimation de prix, ou repondre a vos questions. Par ou voulez-vous commencer ?\n\n"
            "NOS SERVICES ET TARIFS :\n"
            "- Site web personnalise : 100$ a 400$ (setup) + 20$ a 40$/mois. Comprend des mises a jour frequentes et des ajustements selon les demandes du client.\n"
            "- Chatbot IA personnalise : 250$ a 600$ (setup) + 35$ a 60$/mois. Chatbot intelligent integre sur le site du client, disponible 24/7.\n\n"
            "COLLECTE DE LEADS — TRES IMPORTANT :\n"
            "Quand un visiteur exprime un interet concret (veut un devis, parle de son projet, pose des questions sur les prix, veut etre contacte), "
            "tu dois collecter ses coordonnees en 3 etapes separees, une question a la fois :\n"
            "1. Demande son nom complet : 'Pour vous envoyer une soumission, puis-je avoir votre nom ?'\n"
            "2. Demande son email : 'Parfait [prenom] ! Quel est votre courriel ?'\n"
            "3. Demande son telephone : 'Et votre numero de telephone ? (optionnel, vous pouvez ignorer)'\n"
            "Une fois les 3 etapes completees, reponds UNIQUEMENT avec ce JSON exact, sans aucun autre texte :\n"
            "{\"lead\": {\"nom\": \"...\", \"email\": \"...\", \"telephone\": \"...\"}}\n"
            "Si le telephone est refuse, mets 'non fourni'.\n\n"
            "COMPORTEMENT :\n"
            "- Reponds en francais, de facon concise et chaleureuse (2-3 phrases max)\n"
            "- A la fin de chaque reponse, propose toujours une action suivante.\n"
            "- Guide subtilement le client vers une prise de contact ou un devis\n"
            "- Si le client hesite, mets en valeur le rapport qualite-prix et la disponibilite 24/7\n\n"
            "CONTACT : Pour tout devis precis, invite a ecrire a uio.automatisationia@gmail.com ou sur Instagram @uio.automation"
        )
    },
    "demo": {
        "nom": "Assistant Demo",
        "couleur": "#1D9E75",
        "suggestions": ["Nos services", "Nos tarifs", "Comment ca marche ?"],
        "lead_email": os.environ.get("GMAIL_USER", ""),
        "lead_sheet_id": os.environ.get("GOOGLE_SHEET_ID", ""),
        "system_prompt": (
            "Tu es un assistant de demonstration pour UIO Automatisation. Montre les capacites du chatbot de facon professionnelle. Reponds en francais.\n\n"
            "MESSAGE D ACCUEIL : Quand tu recois le message [INIT], presente-toi : "
            "Bonjour ! Je suis l'assistant de demonstration UIO. Comment puis-je vous aider ?\n\n"
            "COLLECTE DE LEADS — TRES IMPORTANT :\n"
            "Quand un visiteur exprime un interet concret, collecte ses coordonnees en 3 etapes separees :\n"
            "1. Nom complet\n2. Email\n3. Telephone (optionnel)\n"
            "Une fois les 3 etapes completees, reponds UNIQUEMENT avec ce JSON exact, sans aucun autre texte :\n"
            "{\"lead\": {\"nom\": \"...\", \"email\": \"...\", \"telephone\": \"...\"}}\n"
            "Si le telephone est refuse, mets 'non fourni'.\n"
        )
    }
    # Pour ajouter un client :
    # "restaurant_mario": {
    #     "nom": "Assistant Mario",
    #     "couleur": "#e74c3c",
    #     "suggestions": ["Notre menu", "Nos horaires", "Reserver une table"],
    #     "lead_email": "mario@restaurant.com",        # optionnel — laisser "" si non voulu
    #     "lead_sheet_id": "ID_GOOGLE_SHEETS_CLIENT",  # optionnel — laisser "" si non voulu
    #     "system_prompt": "Tu es l'assistant du Restaurant Mario..."
    # }
}


# ─── GOOGLE SHEETS ────────────────────────────────────────────────────────────

def get_sheets_token():
    """Obtient un token OAuth2 pour Google Sheets via le compte de service."""
    if not GOOGLE_CREDS_JSON:
        return None
    try:
        import base64
        import time
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        creds        = json.loads(GOOGLE_CREDS_JSON)
        private_key  = creds["private_key"]
        client_email = creds["client_email"]

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()

        now = int(time.time())
        payload = base64.urlsafe_b64encode(
            json.dumps({
                "iss":   client_email,
                "scope": "https://www.googleapis.com/auth/spreadsheets",
                "aud":   "https://oauth2.googleapis.com/token",
                "exp":   now + 3600,
                "iat":   now
            }).encode()
        ).rstrip(b"=").decode()

        key = serialization.load_pem_private_key(private_key.encode(), password=None)
        signature = base64.urlsafe_b64encode(
            key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
        ).rstrip(b"=").decode()

        jwt_token = f"{header}.{payload}.{signature}"

        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion":  jwt_token
            }
        )
        return token_response.json().get("access_token")
    except Exception as e:
        print(f"Erreur token Google: {e}")
        return None


def ajouter_lead_sheets(lead: dict, client_id: str, sheet_id: str):
    """Ajoute une ligne de lead dans le Google Sheets du client."""
    if not sheet_id:
        return False
    try:
        token = get_sheets_token()
        if not token:
            return False

        now    = datetime.now().strftime("%d/%m/%Y %H:%M")
        values = [[
            now,
            client_id,
            lead.get("nom", ""),
            lead.get("email", ""),
            lead.get("telephone", "")
        ]]

        response = requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/A:E:append",
            headers={"Authorization": f"Bearer {token}"},
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            json={"values": values}
        )
        print(f"Sheets response: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur Sheets: {e}")
        return False


# ─── EMAIL ────────────────────────────────────────────────────────────────────

def envoyer_email_lead(lead: dict, client_id: str, destinataire: str):
    """Envoie un email de notification quand un lead est capturé."""
    if not GMAIL_USER or not GMAIL_PASSWORD or not destinataire:
        print("Gmail non configure — email non envoye")
        return False
    try:
        sujet = f"Nouveau lead — {lead.get('nom', 'Inconnu')} ({client_id})"
        corps = f"""
Nouveau lead capturé via le chatbot !

Client ID  : {client_id}
Nom        : {lead.get('nom', 'N/A')}
Email      : {lead.get('email', 'N/A')}
Téléphone  : {lead.get('telephone', 'N/A')}
Heure      : {datetime.now().strftime('%A %d %B %Y à %H:%M')}

Réponds rapidement pour maximiser tes chances de conversion !
— UIO Automation Bot
"""
        msg = MIMEMultipart()
        msg["From"]    = GMAIL_USER
        msg["To"]      = destinataire
        msg["Subject"] = sujet
        msg.attach(MIMEText(corps, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)

        print(f"Email lead envoye a {destinataire} pour {lead.get('nom')}")
        return True
    except Exception as e:
        print(f"Erreur email: {e}")
        return False


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return "UIO Backend actif"


@app.route("/chat", methods=["POST"])
def chat():
    data      = request.json
    messages  = data.get("messages", [])
    client_id = data.get("client_id", "uio")
    client    = CLIENTS.get(client_id, CLIENTS["uio"])

    if len(messages) > 20:
        return jsonify({
            "choices": [{
                "message": {
                    "content": "Vous avez atteint la limite de cette conversation. Contactez-nous directement pour continuer."
                }
            }]
        })

    now = datetime.now().strftime("%A %d %B %Y, %H:%M")
    system = {
        "role": "system",
        "content": client["system_prompt"] + "\n\nDate et heure actuelle : " + now
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + OPENAI_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "max_tokens": 300,
            "messages": [system] + messages
        }
    )
    result = response.json()

    # Détecter si la réponse contient un lead JSON
    try:
        reply_text = result["choices"][0]["message"]["content"].strip()
        if '{"lead"' in reply_text:
            start     = reply_text.index('{"lead"')
            end       = reply_text.index('}', start) + 1
            lead_data = json.loads(reply_text[start:end])

            if "lead" in lead_data:
                lead         = lead_data["lead"]
                destinataire = client.get("lead_email", "")
                sheet_id     = client.get("lead_sheet_id", "")

                # Email (si configuré)
                if destinataire:
                    envoyer_email_lead(lead, client_id, destinataire)

                # Google Sheets (si configuré)
                if sheet_id:
                    ajouter_lead_sheets(lead, client_id, sheet_id)

                # Remplacer le JSON par un message chaleureux
                result["choices"][0]["message"]["content"] = (
                    f"Merci {lead.get('nom', '')} ! 🎉 "
                    "Vos coordonnées ont bien été reçues. "
                    "Un membre de l'équipe vous contactera très bientôt. "
                    "Avez-vous d'autres questions en attendant ?"
                )
                result["lead_captured"] = True
    except Exception as e:
        print(f"Erreur detection lead: {e}")

    return jsonify(result)


@app.route("/chatbot.js")
def chatbot_js():
    client_id   = request.args.get("client", "uio")
    client      = CLIENTS.get(client_id, CLIENTS["uio"])
    couleur     = client["couleur"]
    nom         = client["nom"]
    suggestions = client.get("suggestions", ["Nos services", "Nos tarifs", "Comment ca marche ?"])
    backend     = request.host_url.rstrip("/")

    sugg_html = ""
    for s in suggestions:
        sugg_html += '<button class=\\"uio-sugg\\" onclick=\\"suggClick(this)\\">' + s + '</button>'

    js = ("""
(function() {
  var CLIENT_ID = '""" + client_id + """';
  var NOM = '""" + nom + """';
  var COULEUR = '""" + couleur + """';
  var BACKEND = '""" + backend + """';
  var history = [];
  var initialized = false;

  var style = document.createElement('style');
  style.textContent = `
    #uio-btn { position:fixed; bottom:24px; right:24px; width:56px; height:56px; border-radius:50%; background:""" + couleur + """; border:none; cursor:pointer; box-shadow:0 4px 20px rgba(0,0,0,0.2); z-index:9999; display:flex; align-items:center; justify-content:center; }
    #uio-box { position:fixed; bottom:92px; right:24px; width:340px; height:480px; background:#fff; border-radius:16px; box-shadow:0 8px 40px rgba(0,0,0,0.18); display:none; flex-direction:column; z-index:9999; overflow:hidden; font-family:sans-serif; }
    #uio-head { background:""" + couleur + """; padding:14px 18px; color:#fff; font-weight:600; font-size:15px; display:flex; align-items:center; gap:10px; }
    #uio-online { width:8px; height:8px; border-radius:50%; background:#5DCAA5; }
    #uio-msgs { flex:1; overflow-y:auto; padding:14px; display:flex; flex-direction:column; gap:10px; }
    .uio-bubble { max-width:80%; padding:9px 13px; border-radius:12px; font-size:13px; line-height:1.5; }
    .uio-bot { background:#f1f0f0; color:#111; align-self:flex-start; border-bottom-left-radius:3px; }
    .uio-user { background:""" + couleur + """; color:#fff; align-self:flex-end; border-bottom-right-radius:3px; }
    #uio-suggestions { display:flex; flex-direction:column; gap:6px; margin-top:8px; }
    .uio-sugg { background:transparent; border:1px solid """ + couleur + """; color:""" + couleur + """; border-radius:20px; padding:6px 14px; font-size:12px; cursor:pointer; text-align:left; transition:all .2s; }
    .uio-sugg:hover { background:""" + couleur + """; color:#fff; }
    #uio-input-row { display:flex; gap:8px; padding:10px; border-top:1px solid #eee; }
    #uio-input { flex:1; border:1px solid #ddd; border-radius:8px; padding:8px 12px; font-size:13px; outline:none; }
    #uio-send { background:""" + couleur + """; color:#fff; border:none; border-radius:8px; padding:8px 14px; cursor:pointer; font-size:13px; }
    #uio-lead-banner { background:#e8f5e9; border-top:2px solid #4CAF50; padding:8px 14px; font-size:12px; color:#2e7d32; display:none; text-align:center; }
  `;
  document.head.appendChild(style);

  var btn = document.createElement('button');
  btn.id = 'uio-btn';
  btn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>';
  document.body.appendChild(btn);

  var box = document.createElement('div');
  box.id = 'uio-box';
  box.innerHTML = `
    <div id="uio-head"><div id="uio-online"></div>` + NOM + `</div>
    <div id="uio-msgs"></div>
    <div id="uio-lead-banner">✅ Vos coordonnées ont été transmises !</div>
    <div id="uio-input-row">
      <input id="uio-input" placeholder="Votre message..."/>
      <button id="uio-send">Envoyer</button>
    </div>`;
  document.body.appendChild(box);

  btn.onclick = function() {
    var isOpen = box.style.display === 'flex';
    box.style.display = isOpen ? 'none' : 'flex';
    if (!isOpen && !initialized) {
      initialized = true;
      sendInit();
    }
  };

  async function sendInit() {
    var typing = addBubble('...', 'bot');
    try {
      var res = await fetch(BACKEND + '/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({messages: [{role:'user', content:'[INIT]'}], client_id: CLIENT_ID})
      });
      var data = await res.json();
      typing.remove();
      var reply = data.choices[0].message.content;
      addBubble(reply, 'bot');
      // Ajouter les suggestions après le message de bienvenue
      var sugg = document.createElement('div');
      sugg.id = 'uio-suggestions';
      sugg.innerHTML = '""" + sugg_html + """';
      document.getElementById('uio-msgs').appendChild(sugg);
    } catch(e) {
      typing.remove();
      addBubble('Bonjour ! Comment puis-je vous aider ?', 'bot');
    }
  }

  window.suggClick = function(btn) {
    var text = btn.textContent;
    var sugg = document.getElementById('uio-suggestions');
    if (sugg) sugg.remove();
    document.getElementById('uio-input').value = text;
    sendMsg();
  };

  function addBubble(text, role) {
    var d = document.createElement('div');
    d.className = 'uio-bubble ' + (role === 'user' ? 'uio-user' : 'uio-bot');
    d.textContent = text;
    document.getElementById('uio-msgs').appendChild(d);
    document.getElementById('uio-msgs').scrollTop = 99999;
    return d;
  }

  document.getElementById('uio-send').onclick = sendMsg;
  document.getElementById('uio-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendMsg();
  });

  async function sendMsg() {
    var input = document.getElementById('uio-input');
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    addBubble(text, 'user');
    history.push({role:'user', content:text});
    var typing = addBubble('...', 'bot');
    try {
      var res = await fetch(BACKEND + '/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({messages: history, client_id: CLIENT_ID})
      });
      var data = await res.json();
      typing.remove();
      var reply = data.choices[0].message.content;
      addBubble(reply, 'bot');
      history.push({role:'assistant', content:reply});

      if (data.lead_captured) {
        var banner = document.getElementById('uio-lead-banner');
        if (banner) { banner.style.display = 'block'; setTimeout(function(){ banner.style.display = 'none'; }, 5000); }
      }
    } catch(e) {
      typing.remove();
      addBubble('Erreur de connexion. Veuillez reessayer.', 'bot');
    }
  }
})();
""")
    return Response(js, mimetype="application/javascript")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
