import os
from fastapi import FastAPI, HTTPException
import requests

app = FastAPI()

# CORRECTO: Aquí leemos los nombres de las variables de entorno de Railway
CLIENT_ID = os.environ.get("ROBLOX_CLIENT_ID")
CLIENT_SECRET = os.environ.get("ROBLOX_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("ROBLOX_REDIRECT_URI")

@app.get("/")
async def root():
    return {"status": "Servidor de verificación activo"}

@app.get("/callback")
async def roblox_callback(code: str, state: str):
    discord_id = state

    token_url = "https://apis.roblox.com/oauth/v1/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

resp = requests.post(token_url, data=payload)
if resp.status_code != 200:
    print("RESPUESTA DE ROBLOX:", resp.text)
    raise HTTPException(status_code=400, detail="Error al autenticar con Roblox")

    token_data = resp.json()
    access_token = token_data.get("access_token")

    userinfo_resp = requests.get(
        "https://apis.roblox.com/oauth/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="No se pudo obtener la información del usuario")

    user_info = userinfo_resp.json()
    roblox_id = user_info.get("sub")

    return {"success": True, "roblox_id": roblox_id, "discord_id": discord_id}
