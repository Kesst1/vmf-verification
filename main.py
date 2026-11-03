import os
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

# Credenciales de Roblox desde Railway
CLIENT_ID = os.environ.get("ROBLOX_CLIENT_ID")
CLIENT_SECRET = os.environ.get("ROBLOX_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("ROBLOX_REDIRECT_URI")

# Credenciales de Discord para asignar roles desde la web
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = os.environ.get("GUILD_ID")
VERIFIED_ROLE_ID = os.environ.get("VERIFIED_ROLE_ID")

def init_db():
    conn = sqlite3.connect("verification.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verified_users (
            discord_id INTEGER PRIMARY KEY,
            roblox_id INTEGER UNIQUE
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/")
async def root():
    return {"status": "Servidor de verificación activo"}

@app.get("/callback", response_class=HTMLResponse)
async def roblox_callback(code: str, state: str):
    discord_id = state

    # 1. Intercambiar código por token de acceso en Roblox
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
        return HTMLResponse(content="<h3 style='color:white; text-align:center; font-family:sans-serif; margin-top:20vh;'>Error al autenticar con Roblox</h3>", status_code=400)

    token_data = resp.json()
    access_token = token_data.get("access_token")

    # 2. Obtener la información del usuario de Roblox
    userinfo_resp = requests.get(
        "https://apis.roblox.com/oauth/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if userinfo_resp.status_code != 200:
        return HTMLResponse(content="<h3 style='color:white; text-align:center; font-family:sans-serif; margin-top:20vh;'>No se pudo obtener la información del usuario</h3>", status_code=400)

    user_info = userinfo_resp.json()
    roblox_id = user_info.get("sub")

    # 3. Guardar en la base de datos SQLite
    try:
        conn = sqlite3.connect("verification.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO verified_users (discord_id, roblox_id) VALUES (?, ?)",
            (int(discord_id), int(roblox_id))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print("Error guardando en base de datos:", e)

    # 4. Asignar el rol en Discord automáticamente mediante la API REST
    if DISCORD_TOKEN and GUILD_ID and VERIFIED_ROLE_ID:
        role_url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{discord_id}/roles/{VERIFIED_ROLE_ID}"
        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json"
        }
        role_resp = requests.put(role_url, headers=headers)
        if role_resp.status_code not in (200, 204):
            print("No se pudo asignar el rol en Discord:", role_resp.text)

    # 5. Mostrar la página web de éxito optimizada
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verificación Exitosa - VMF</title>
        <style>
            body {
                margin: 0;
                padding: 0;
                height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(rgba(0,0,0,0.65), rgba(0,0,0,0.65)), url('https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1920&auto=format&fit=crop') no-repeat center center fixed;
                background-size: cover;
                color: white;
                text-align: center;
            }
            .card {
                background: rgba(18, 18, 20, 0.85);
                padding: 45px 35px;
                border-radius: 16px;
                box-shadow: 0 15px 35px rgba(0,0,0,0.6);
                max-width: 420px;
                width: 90%;
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.1);
            }
            .icon {
                font-size: 50px;
                margin-bottom: 15px;
            }
            h1 {
                font-size: 22px;
                margin-bottom: 15px;
                letter-spacing: 1px;
                color: #2ecc71;
            }
            p {
                color: #b0b0b0;
                font-size: 14px;
                margin-bottom: 30px;
                line-height: 1.5;
            }
            .btn {
                display: inline-block;
                background-color: #5865F2;
                color: white;
                padding: 12px 28px;
                font-size: 14px;
                font-weight: bold;
                text-decoration: none;
                border-radius: 8px;
                transition: background 0.3s ease, transform 0.2s ease;
                box-shadow: 0 4px 15px rgba(88, 101, 242, 0.4);
            }
            .btn:hover {
                background-color: #4752C4;
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">🎉</div>
            <h1>VERIFICATION SUCCESSFUL</h1>
            <p>Tu cuenta de Roblox se ha vinculado con éxito y ya se te ha otorgado el rol en el servidor. ¡Ya puedes volver a Discord!</p>
            <a href="https://discord.com/channels/@me" class="btn">GO BACK TO DISCORD</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
