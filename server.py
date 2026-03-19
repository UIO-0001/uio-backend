# On importe les outils dont on a besoin
# Flask = le serveur web
# Response = pour envoyer du JavaScript
# CORS = permet au site HTML d'appeler ce serveur
# datetime = pour la date et l'heure
# requests = pour appeler l'API OpenAI
# os = pour lire les variables d'environnement (clé API)
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime
import requests
import os

# On crée l'application Flask
app = Flask(__name__)
CORS(app)

# On lit la clé API depuis les variables d'environnement de Render
# Elle n'est jamais écrite dans le code — c'est pour ça qu'elle est sécurisée
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ── LISTE DE VOS CLIENTS ──────────────────────────────────────────
# Pour ajouter un nouveau client, copiez un bloc et changez les infos
# client_id = l'identifiant unique utilisé dans le lien d'installation
CLIENTS = {
    "uio": {
        "nom": "Assistant UIO",
        "couleur": "#7c5cfc",
        "system_prompt": "system_prompt": """Tu es l'assistant IA de UIO Automatisation, une entreprise québécoise spécialisée en chatbots IA et sites web pour les petites entreprises.
MESSAGE D'ACCUEIL : À la toute première interaction présente-toi ainsi :
'Bonjour ! Je suis l'assistant IA de UIO 👋 Je peux vous aider à découvrir nos services, obtenir une estimation de prix, ou répondre à vos questions. Par où voulez-vous commencer ?'
NOS SERVICES ET TARIFS :
- Site web personnalisé : 100$ à 400$ (setup) + 20$ à 40$/mois. Comprend des mises à jour fréquentes et des ajustements selon les demandes du client.
- Chatbot IA personnalisé : 250$ à 600$ (setup) + 35$ à 60$/mois. Chatbot intelligent intégré sur le site du client, disponible 24/7.
COMPORTEMENT :
- Réponds en français, de façon concise et chaleureuse (2-3 phrases max)
- À la fin de chaque réponse, propose toujours une action suivante. Ex : 'Voulez-vous une estimation pour votre projet ?' ou 'Je peux vous expliquer comment fonctionne l'installation, cela vous intéresse ?'
- Guide subtilement le client vers une prise de contact ou un devis
- Si le client hésite, mets en valeur le rapport qualité-prix et la disponibilité 24/7
CONTACT : Pour tout devis précis ou question complexe, invite à écrire à uio.automatisationia@gmail.com ou sur Instagram @uio.automation"""
    },
    "demo": {
        "nom": "Assistant Demo",
        "couleur": "#1D9E75",
        "system_prompt": "Tu es un assistant de démonstration pour UIO Automatisation. Montre les capacités du chatbot de façon professionnelle. Réponds en français."
    }
    # Exemple de futur client :
    # "restaurant_mario": {
    #     "nom": "Assistant Mario",
    #     "couleur": "#e74c3c",
    #     "system_prompt": "Tu es l'assistant du Restaurant Mario..."
    # }
}


# ── ROUTE D'ACCUEIL ───────────────────────────────────────────────
# C'est juste une page qui dit "je suis vivant"
# UptimeRobot ping cette URL toutes les 5 minutes
# Sans ça, UptimeRobot pensait que le serveur était mort
@app.route("/")
def home():
    return "UIO Backend actif"


# ── ROUTE PRINCIPALE DU CHAT ──────────────────────────────────────
# C'est ici que les messages des visiteurs arrivent
# et qu'on les envoie à OpenAI
@app.route("/chat", methods=["POST"])
def chat():
    # On lit les données envoyées par le chatbot
    data = request.json
    messages = data.get("messages", [])

    # On identifie quel client envoie la requête
    # Si on ne reconnaît pas le client, on utilise "uio" par défaut
    client_id = data.get("client_id", "uio")
    client = CLIENTS.get(client_id, CLIENTS["uio"])

    # Limite de 20 messages par conversation
    # Protège contre les abus et les coûts excessifs
    if len(messages) > 20:
        return jsonify({
            "choices": [{
                "message": {
                    "content": "Vous avez atteint la limite de cette conversation. Contactez-nous directement pour continuer."
                }
            }]
        })

    # On ajoute automatiquement la date et l'heure au prompt
    # Comme ça le chatbot sait toujours quelle heure il est
    now = datetime.now().strftime("%A %d %B %Y, %H:%M")
    system = {
        "role": "system",
        "content": client["system_prompt"] + "\n\nDate et heure actuelle : " + now
    }

    # On envoie le tout à OpenAI
    # gpt-4o-mini = moins cher, presque aussi bon que gpt-4o
    # max_tokens = longueur maximale de la réponse
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
    return jsonify(response.json())


# ── ROUTE DU WIDGET JAVASCRIPT ────────────────────────────────────
# C'est ici que la magie opère !
# Quand un site client charge le script, cette route génère
# le JavaScript personnalisé avec les bonnes couleurs et le bon nom
@app.route("/chatbot.js")
def chatbot_js():
    # On lit l'identifiant client dans l'URL
    # ex: /chatbot.js?client=restaurant_mario
    client_id = request.args.get("client", "uio")
    client = CLIENTS.get(client_id, CLIENTS["uio"])
    couleur = client["couleur"]
    nom = client["nom"]

    # L'URL du serveur — utilisée par le widget pour envoyer les messages
    backend = request.host_url.rstrip("/")

    # Le JavaScript qui sera injecté dans le site du client
    # Ce code crée le bouton 💬 et la fenêtre de chat
    js = """
(function() {
  var CLIENT_ID = '""" + client_id + """';
  var NOM = '""" + nom + """';
  var COULEUR = '""" + couleur + """';
  var BACKEND = '""" + backend + """';
  var history = [];

  var style = document.createElement('style');
  style.textContent = `
    #uio-btn { position:fixed; bottom:24px; right:24px; width:56px; height:56px; border-radius:50%; background:` + couleur + `; border:none; cursor:pointer; box-shadow:0 4px 20px rgba(0,0,0,0.2); font-size:24px; z-index:9999; }
    #uio-box { position:fixed; bottom:92px; right:24px; width:340px; height:480px; background:#fff; border-radius:16px; box-shadow:0 8px 40px rgba(0,0,0,0.18); display:none; flex-direction:column; z-index:9999; overflow:hidden; font-family:sans-serif; }
    #uio-head { background:` + couleur + `; padding:14px 18px; color:#fff; font-weight:600; font-size:15px; display:flex; align-items:center; gap:10px; }
    #uio-online { width:8px; height:8px; border-radius:50%; background:#5DCAA5; }
    #uio-msgs { flex:1; overflow-y:auto; padding:14px; display:flex; flex-direction:column; gap:10px; }
    .uio-bubble { max-width:80%; padding:9px 13px; border-radius:12px; font-size:13px; line-height:1.5; }
    .uio-bot { background:#f1f0f0; color:#111; align-self:flex-start; border-bottom-left-radius:3px; }
    .uio-user { background:` + couleur + `; color:#fff; align-self:flex-end; border-bottom-right-radius:3px; }
    #uio-input-row { display:flex; gap:8px; padding:10px; border-top:1px solid #eee; }
    #uio-input { flex:1; border:1px solid #ddd; border-radius:8px; padding:8px 12px; font-size:13px; outline:none; }
    #uio-send { background:` + couleur + `; color:#fff; border:none; border-radius:8px; padding:8px 14px; cursor:pointer; font-size:13px; }
  `;
  document.head.appendChild(style);

  var btn = document.createElement('button');
  btn.id = 'uio-btn';
  btn.textContent = '💬';
  document.body.appendChild(btn);

  var box = document.createElement('div');
  box.id = 'uio-box';
  box.innerHTML = '<div id="uio-head"><div id="uio-online"></div>' + NOM + '</div><div id="uio-msgs"><div class="uio-bubble uio-bot">Bonjour ! Comment puis-je vous aider ?</div></div><div id="uio-input-row"><input id="uio-input" placeholder="Votre message..."/><button id="uio-send">Envoyer</button></div>';
  document.body.appendChild(box);

  btn.onclick = function() {
    box.style.display = box.style.display === 'flex' ? 'none' : 'flex';
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
    } catch(e) {
      typing.remove();
      addBubble('Erreur de connexion. Veuillez réessayer.', 'bot');
    }
  }
})();
"""
    return Response(js, mimetype="application/javascript")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)