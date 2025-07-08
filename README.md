ParkPing - Project

## Features
- Google Maps integration
- User registration/login (SQLite)
- Book parking by hour
- Mock payment tracking
- Responsive frontend (Bootstrap-ready)

## Setup
1. `pip install flask werkzeug`
2. Replace `YOUR_API_KEY` in `index.html`
3. Run:
```bash
cd backend
python app.py
```
Open http://localhost:5000


## Get a Google Maps API Key

Go to: https://console.cloud.google.com/
1. Create or select a project.
2. Navigate to APIs & Services > Credentials.
3. Click "Create credentials" > API key.
4. Copy the key ( paste this into your HTML file index.html).
Here in this line `<script src="https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY&callback=initMap" async defer></script>`

IMPORTANT: Make sure you've enabled the Maps JavaScript API for your project:
5. Go to APIs & Services > Library
6. Search for “Maps JavaScript API”
7. Click it → Click Enable

Here's what the front page looks like if you're too lazy to open the project yourself:
User View:

![image](https://github.com/user-attachments/assets/eefb268d-dcdf-4c9b-9c3a-8d6f9c0c67e6)

Organizer View:

![image](https://github.com/user-attachments/assets/85b843a4-e942-4ca6-9395-59720ae92d60)
