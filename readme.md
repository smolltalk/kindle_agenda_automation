# Kindle Agenda

Génère une image 600×800 en niveaux de gris pour un Kindle 4, affichant l'agenda du jour (ou de demain après 18h30), la météo de Vannes et les marées de Saint-Armel.

## Contenu de l'image

- **Date** — "Aujourd'hui" ou "Demain" selon l'heure
- **Météo Vannes** — Température, humidité, vent, prévisions min/max, précipitations, icône WMO (via [Open-Meteo](https://open-meteo.com/), sans clé API)
- **Marées Saint-Armel** — Horaires PM/BM, hauteurs, coefficient (scraping [maree.info/108](https://maree.info/108))
- **Agenda** — Événements Google Calendar du jour

## Prérequis

### Python 3.10+

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib pillow
```

### Polices TrueType

Le script cherche automatiquement une police dans cet ordre :

1. `arial.ttf` (Windows)
2. `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` (Debian / Raspberry Pi OS)
3. `/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf` (Fedora)
4. `/usr/share/fonts/TTF/DejaVuSans.ttf` (Arch)

Sur Raspberry Pi / Debian, installer le paquet :

```bash
sudo apt install fonts-dejavu-core
```

### Google Calendar API

1. Créer un projet sur [Google Cloud Console](https://console.cloud.google.com/)
2. Activer l'API Google Calendar
3. Créer des identifiants OAuth 2.0 et télécharger `credentials.json`
4. Placer `credentials.json` à la racine du projet
5. Au premier lancement, le navigateur s'ouvre pour autoriser l'accès — un fichier `token.json` est généré automatiquement

## Utilisation

```bash
python generate_agenda_image.py
```

L'image est générée dans `output/agenda_du_jour.png`.

## Exécution automatique (cron)

Exemple sur Raspberry Pi :

```cron
30 6  * * *  cd /home/pi/kindle-automation && python generate_agenda_image.py
45 18 * * *  cd /home/pi/kindle-automation && python generate_agenda_image.py
```