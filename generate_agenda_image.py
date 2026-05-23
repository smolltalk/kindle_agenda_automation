import datetime
import os
import re
import urllib.request
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

# Si vous modifiez ces champs d'application, supprimez le fichier token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def is_evening():
    """Retourne True si l'heure actuelle est >= 18:30 (heure locale)."""
    now = datetime.datetime.now()
    return now.hour > 18 or (now.hour == 18 and now.minute >= 30)

def target_date():
    """Retourne la date cible : demain si après 18:30, sinon aujourd'hui."""
    if is_evening():
        return datetime.date.today() + datetime.timedelta(days=1)
    return datetime.date.today()

def get_calendar_events():
    creds = None
    # Le fichier token.json stocke les identifiants d'accès de l'utilisateur.
    # Il est créé automatiquement lors de la première connexion.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si les identifiants ne sont pas valides, on demande à l'utilisateur de se connecter.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Enregistre les identifiants pour la prochaine exécution
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    # Définir le début et la fin de la journée cible
    jour_cible = target_date()
    debut_journee = datetime.datetime.combine(jour_cible, datetime.time.min).isoformat() + 'Z'
    fin_journee = datetime.datetime.combine(jour_cible, datetime.time.max).isoformat() + 'Z'

    label = "demain" if is_evening() else "du jour"
    print(f"Récupération des événements {label}...")
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=debut_journee,
        timeMax=fin_journee,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return events_result.get('items', [])

# Codes météo WMO -> descriptions en français
WMO_DESCRIPTIONS = {
    0: "Ciel dégagé", 1: "Peu nuageux", 2: "Partiellement nuageux", 3: "Couvert",
    45: "Brouillard", 48: "Brouillard givrant",
    51: "Bruine légère", 53: "Bruine modérée", 55: "Bruine forte",
    61: "Pluie légère", 63: "Pluie modérée", 65: "Pluie forte",
    66: "Pluie verglaçante légère", 67: "Pluie verglaçante forte",
    71: "Neige légère", 73: "Neige modérée", 75: "Neige forte",
    77: "Grains de neige", 80: "Averses légères", 81: "Averses modérées",
    82: "Averses violentes", 85: "Averses de neige légères", 86: "Averses de neige fortes",
    95: "Orage", 96: "Orage avec grêle légère", 99: "Orage avec grêle forte",
}

def get_tides_vannes():
    """Récupère les marées pour la date cible depuis maree.info/108."""
    url = "https://maree.info/108"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")

        # Supprimer les balises HTML pour obtenir le texte brut
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)

        date_cible = target_date()
        jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        jour = jours[date_cible.weekday()]
        day = date_cible.day

        # Chercher la ligne du jour, s'arrêter au jour suivant
        match = re.search(
            rf'{jour}\.\s*{day}\b(.+?)(?=(?:Lun|Mar|Mer|Jeu|Ven|Sam|Dim)\.\s*\d|\Z)', text
        )
        if not match:
            print("Marées : ligne du jour introuvable.")
            return None

        bloc = match.group(1)

        times = re.findall(r'(\d{2}h\d{2})', bloc)
        heights_raw = re.findall(r'(\d+,\d+)\s*m', bloc)

        if not times or len(times) != len(heights_raw):
            print("Marées : données incomplètes.")
            return None

        tides = []
        for t, h in zip(times, heights_raw):
            height = float(h.replace(',', '.'))
            tide_type = "PM" if height >= 1.5 else "BM"
            tides.append({
                "type": tide_type,
                "time": t.replace('h', ':'),
                "height": height,
            })

        # Extraire le coefficient (premiers chiffres après les hauteurs)
        after_heights = bloc[bloc.rfind('m') + 1:]
        coeffs = re.findall(r'(\d{2,3})', after_heights)
        coeff = coeffs[0] if coeffs else None

        return {"tides": tides, "coeff": coeff}
    except Exception as e:
        print(f"Impossible de récupérer les marées : {e}")
        return None

def draw_weather_icon(draw, code, cx, cy, size=50):
    """Dessine une icône météo simple basée sur le code WMO."""
    import math
    r = size // 2
    dark = 40
    mid = 120
    light = 180

    def draw_sun(ox, oy, sr):
        draw.ellipse([ox - sr, oy - sr, ox + sr, oy + sr], fill=dark)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = ox + int((sr + 4) * math.cos(rad))
            y1 = oy + int((sr + 4) * math.sin(rad))
            x2 = ox + int((sr + 10) * math.cos(rad))
            y2 = oy + int((sr + 10) * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=dark, width=2)

    def draw_cloud(ox, oy, scale=1.0):
        s = lambda v: int(v * scale)
        draw.ellipse([ox - s(20), oy - s(10), ox + s(4), oy + s(8)], fill=mid)
        draw.ellipse([ox - s(10), oy - s(18), ox + s(12), oy + s(4)], fill=mid)
        draw.ellipse([ox, oy - s(10), ox + s(22), oy + s(8)], fill=mid)
        draw.rectangle([ox - s(18), oy, ox + s(20), oy + s(8)], fill=mid)

    def draw_rain(ox, oy):
        for dx in [-10, 0, 10]:
            draw.line([(ox + dx, oy), (ox + dx - 3, oy + 10)], fill=dark, width=2)

    def draw_snow(ox, oy):
        for dx in [-10, 0, 10]:
            draw.ellipse([ox + dx - 2, oy - 2, ox + dx + 2, oy + 2], fill=dark)
            draw.ellipse([ox + dx + 3, oy + 7, ox + dx + 7, oy + 11], fill=dark)

    def draw_lightning(ox, oy):
        draw.polygon([(ox, oy), (ox - 4, oy + 10), (ox + 2, oy + 8),
                       (ox - 2, oy + 18), (ox + 6, oy + 6), (ox, oy + 8)], fill=dark)

    if code <= 1:
        draw_sun(cx, cy, r // 2)
    elif code == 2:
        draw_sun(cx - 8, cy - 8, r // 3)
        draw_cloud(cx + 5, cy + 5)
    elif code == 3:
        draw_cloud(cx, cy, 1.2)
    elif code in (45, 48):
        for dy in [-8, 0, 8]:
            draw.line([(cx - 20, cy + dy), (cx + 20, cy + dy)], fill=mid, width=2)
    elif code in (51, 53, 55):
        draw_cloud(cx, cy - 8)
        for dx in [-6, 6]:
            draw.ellipse([cx + dx - 1, cy + 12, cx + dx + 1, cy + 14], fill=dark)
    elif code in (61, 63, 65, 66, 67, 80, 81, 82):
        draw_cloud(cx, cy - 8)
        draw_rain(cx, cy + 12)
    elif code in (71, 73, 75, 77, 85, 86):
        draw_cloud(cx, cy - 8)
        draw_snow(cx, cy + 12)
    elif code in (95, 96, 99):
        draw_cloud(cx, cy - 10)
        draw_lightning(cx, cy + 8)

def get_weather_vannes():
    """Récupère la météo pour Vannes (56000) via Open-Meteo. Après 19h, affiche demain."""
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=47.6558&longitude=-2.7600"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum"
        "&timezone=Europe%2FParis&forecast_days=2"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        current = data["current"]
        daily = data["daily"]
        tomorrow = is_evening()
        idx = 1 if tomorrow else 0
        return {
            "temp": current["temperature_2m"],
            "humidity": current["relative_humidity_2m"],
            "wind": current["wind_speed_10m"],
            "code": current["weather_code"],
            "temp_min": daily["temperature_2m_min"][idx],
            "temp_max": daily["temperature_2m_max"][idx],
            "precip": daily["precipitation_sum"][idx],
            "daily_code": daily["weather_code"][idx],
            "tomorrow": tomorrow,
        }
    except Exception as e:
        print(f"Impossible de récupérer la météo : {e}")
        return None

def generate_schedule_image(events, weather=None, tides=None):
    # Configuration de l'image (Dimensions et Couleurs)
    width, height = 600, 800
    background_color = 245                # Gris très clair
    text_color = 30                       # Anthracite
    accent_color = 60                     # Gris foncé
    line_color = 200                      # Gris bordure

    image = Image.new("L", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Chargement d'une police (utilise une police par défaut si non trouvée)
    try:
        # Sur Windows: "arial.ttf", Sur macOS/Linux: "Arial.ttf" ou chemins complets
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_text = ImageFont.truetype("arial.ttf", 18)
        font_time = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font_title = font_text = font_time = ImageFont.load_default()

    # Dessiner le titre
    date_cible = target_date()
    date_str = date_cible.strftime("%d / %m / %Y")
    label_jour = "Demain" if is_evening() else "Aujourd'hui"
    draw.text((40, 30), f"{label_jour} — {date_str}", fill=accent_color, font=font_title)
    draw.line([(40, 70), (width - 40, 70)], fill=accent_color, width=3)

    y_position = 100

    # Section météo
    if weather:
        meteo_y_start = y_position
        meteo_label = "Météo Vannes"
        if weather.get("tomorrow"):
            meteo_label += " — Demain"
        draw.text((40, y_position), meteo_label, fill=accent_color, font=font_title)
        y_position += 40

        if not weather.get("tomorrow"):
            desc = WMO_DESCRIPTIONS.get(weather["code"], "Inconnu")
            draw.text((40, y_position), f"Actuellement : {weather['temp']}°C — {desc}", fill=text_color, font=font_text)
            y_position += 30
            draw.text((40, y_position), f"Humidité : {weather['humidity']}%    Vent : {weather['wind']} km/h", fill=100, font=font_time)
            y_position += 30

        desc_jour = WMO_DESCRIPTIONS.get(weather["daily_code"], "Inconnu")
        prevision = "Prévisions" if weather.get("tomorrow") else "Journée"
        draw.text((40, y_position), f"{prevision} : {weather['temp_min']}° / {weather['temp_max']}° — {desc_jour}", fill=text_color, font=font_text)
        y_position += 30
        draw.text((40, y_position), f"Précipitations : {weather['precip']} mm", fill=100, font=font_time)
        y_position += 20

        # Icône météo tendance du jour (côté droit)
        draw_weather_icon(draw, weather["daily_code"], width - 80, meteo_y_start + 75, size=70)

    # Section marées
    if tides:
        y_position += 20
        draw.line([(40, y_position), (width - 40, y_position)], fill=accent_color, width=3)
        y_position += 15
        titre_marees = "Marées St-Armel"
        if tides.get("coeff"):
            titre_marees += f"  (coeff. {tides['coeff']})"
        draw.text((40, y_position), titre_marees, fill=accent_color, font=font_title)
        y_position += 40

        for tide in tides["tides"]:
            if y_position > height - 40:
                break
            label = "Pleine mer" if tide["type"] == "PM" else "Basse mer"
            draw.text((40, y_position), tide["time"], fill=100, font=font_time)
            draw.text((120, y_position), f"{label}  ({tide['height']} m)", fill=text_color, font=font_text)
            y_position += 30

    # Section agenda
    y_position += 20
    draw.line([(40, y_position), (width - 40, y_position)], fill=accent_color, width=3)
    y_position += 15
    draw.text((40, y_position), "Agenda", fill=accent_color, font=font_title)
    y_position += 40

    if not events:
        draw.text((40, y_position), "Aucun événement de prévu aujourd'hui.", fill=120, font=font_text)
    else:
        for event in events:
            if y_position > height - 60:
                draw.text((40, y_position), "... et d'autres événements", fill=120, font=font_text)
                break

            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            if 'T' in start:
                heure_debut = start.split('T')[1][:5]
                heure_fin = end.split('T')[1][:5]
                time_str = f"{heure_debut} - {heure_fin}"
            else:
                time_str = "Journée"

            titre_event = event.get('summary', '(Sans titre)')

            draw.text((40, y_position), time_str, fill=100, font=font_time)
            draw.text((180, y_position), titre_event, fill=text_color, font=font_text)
            
            y_position += 40
            draw.line([(40, y_position), (width - 40, y_position)], fill=line_color, width=1)
            y_position += 20

    # Sauvegarde de l'image
    output_filename = "agenda_du_jour.png"
    image.save(output_filename)
    print(f"Image générée avec succès : {output_filename}")

if __name__ == '__main__':
    try:
        events = get_calendar_events()
        weather = get_weather_vannes()
        tides = get_tides_vannes()
        generate_schedule_image(events, weather, tides)
    except Exception as e:
        print(f"Une erreur est survenue : {e}")