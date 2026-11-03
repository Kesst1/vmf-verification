import os
import sqlite3
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

# Credenciales de Roblox desde Railway
CLIENT_ID = os.environ.get("ROBLOX_CLIENT_ID")
CLIENT_SECRET = os.environ.get("ROBLOX_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("ROBLOX_REDIRECT_URI")

# Credenciales de Discord para gestionar miembros desde la web
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = os.environ.get("GUILD_ID")
VERIFIED_ROLE_ID = os.environ.get("VERIFIED_ROLE_ID")

# Configuración del sistema Anti-Alts (Días mínimos de antigüedad)
MINIMUM_DAYS = 30  # Cambia esto por los días que prefieras

def init_db():
    conn = sqlite3.connect("verification.db")
    cursor = conn.cursor()
    # Usamos roblox_id como PRIMARY KEY o UNIQUE estricto para evitar duplicados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verified_users (
            discord_id TEXT PRIMARY KEY,
            roblox_id TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/")
async def root():
    return {"status": "Verification server active"}

@app.get("/callback", response_class=HTMLResponse)
async def roblox_callback(code: str, state: str):
    discord_id = str(state)

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
        return HTMLResponse(content="<h3 style='color:white; text-align:center; font-family:sans-serif; margin-top:20vh;'>Error authenticating with Roblox</h3>", status_code=400)

    token_data = resp.json()
    access_token = token_data.get("access_token")

    # 2. Obtener la información básica del usuario de Roblox (OAuth)
    userinfo_resp = requests.get(
        "https://apis.roblox.com/oauth/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if userinfo_resp.status_code != 200:
        return HTMLResponse(content="<h3 style='color:white; text-align:center; font-family:sans-serif; margin-top:20vh;'>Failed to retrieve user information</h3>", status_code=400)

    user_info = userinfo_resp.json()
    roblox_id = str(user_info.get("sub"))

    # 3. FILTRO ESTRICTO: Comprobar si esta cuenta de Roblox ya está enlazada a CUALQUIER otro Discord
    conn = sqlite3.connect("verification.db")
    cursor = conn.cursor()
    cursor.execute("SELECT discord_id FROM verified_users WHERE roblox_id = ?", (roblox_id,))
    existing_roblox = cursor.fetchone()
    
    # Comprobar también si este usuario de Discord ya tiene otra cuenta de Roblox vinculada
    cursor.execute("SELECT roblox_id FROM verified_users WHERE discord_id = ?", (discord_id,))
    existing_discord = cursor.fetchone()
    conn.close()

    if (existing_roblox and existing_roblox[0] != discord_id) or existing_discord:
        error_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Verification Denied</title>
            <style>
                body { margin: 0; padding: 0; height: 100vh; display: flex; justify-content: center; align-items: center; font-family: 'Segoe UI', sans-serif; background: #121214; color: white; text-align: center; }
                .card { background: rgba(255,255,255,0.05); padding: 40px; border-radius: 16px; max-width: 400px; border: 1px solid rgba(255,255,255,0.1); }
                h1 { color: #e74c3c; font-size: 20px; margin-bottom: 15px; }
                p { color: #b0b0b0; font-size: 14px; line-height: 1.5; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>VERIFICATION FAILED</h1>
                <p>Either this Roblox account is already linked to another Discord user, or your Discord account is already verified with a different Roblox account.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)

    # 4. Obtener datos públicos de Roblox (Nombre y fecha de creación para Anti-Alts)
    roblox_username = "RobloxUser"
    roblox_api_resp = requests.get(f"https://users.roblox.com/v1/users/{roblox_id}")
    if roblox_api_resp.status_code == 200:
        roblox_data = roblox_api_resp.json()
        roblox_username = roblox_data.get("name", "RobloxUser")
        created_at_str = roblox_data.get("created")
        
        if created_at_str:
            clean_date_str = created_at_str.split(".")[0] + "Z" if "." in created_at_str else created_at_str
            created_at = datetime.strptime(clean_date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            account_age_days = (now - created_at).days

            # Filtro Anti-Alts por antigüedad
            if account_age_days < MINIMUM_DAYS:
                error_html = f"""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <title>Verification Denied</title>
                    <style>
                        body {{ margin: 0; padding: 0; height: 100vh; display: flex; justify-content: center; align-items: center; font-family: 'Segoe UI', sans-serif; background: #121214; color: white; text-align: center; }}
                        .card {{ background: rgba(255,255,255,0.05); padding: 40px; border-radius: 16px; max-width: 400px; border: 1px solid rgba(255,255,255,0.1); }}
                        h1 {{ color: #e74c3c; font-size: 20px; margin-bottom: 15px; }}
                        p {{ color: #b0b0b0; font-size: 14px; line-height: 1.5; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>VERIFICATION FAILED</h1>
                        <p>Your Roblox account is too new to be verified. It must be at least <b>{MINIMUM_DAYS} days old</b> (Current age: {account_age_days} days).</p>
                    </div>
                </body>
                </html>
                """
                return HTMLResponse(content=error_html, status_code=400)

    # 5. Obtener el Display Name exacto de Discord respetando mayúsculas/minúsculas
    discord_display_name = "User"
    if DISCORD_TOKEN:
        disc_user_resp = requests.get(
            f"https://discord.com/api/v10/users/{discord_id}",
            headers={"Authorization": f"Bot {DISCORD_TOKEN}"}
        )
        if disc_user_resp.status_code == 200:
            user_data = disc_user_resp.json()
            # Prioriza global_name (que respeta tal cual las mayúsculas del perfil)
            discord_display_name = user_data.get("global_name") or user_data.get("username", "User")

    # 6. Guardar en la base de datos SQLite de forma segura
    try:
        conn = sqlite3.connect("verification.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO verified_users (discord_id, roblox_id) VALUES (?, ?)",
            (discord_id, roblox_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print("Error saving to database:", e)
        return HTMLResponse(content="<h3 style='color:white; text-align:center; font-family:sans-serif; margin-top:20vh;'>Database error or account already linked.</h3>", status_code=400)

    # 7. Actualizar el apodo respetando las mayúsculas y asignar el rol conservando los anteriores
    if DISCORD_TOKEN and GUILD_ID:
        member_url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{discord_id}"
        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json"
        }
        
        get_member_resp = requests.get(member_url, headers=headers)
        current_roles = []
        if get_member_resp.status_code == 200:
            current_roles = get_member_resp.json().get("roles", [])

        if VERIFIED_ROLE_ID and VERIFIED_ROLE_ID not in current_roles:
            current_roles.append(VERIFIED_ROLE_ID)

        # Apodo con mayúsculas conservadas (limitado a 32 caracteres por Discord)
        new_nickname = f"{discord_display_name} ({roblox_username})"[:32]
        
        payload_data = {
            "nick": new_nickname,
            "roles": current_roles
        }

        member_resp = requests.patch(member_url, json=payload_data, headers=headers)
        if member_resp.status_code not in (200, 204):
            print("Failed to update nickname or assign role in Discord:", member_resp.text)

    # 8. Mostrar la página web de éxito optimizada
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Successful Verification - VMF</title>
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
            <p>Your account has been verified! Your nickname has been updated with your exact profile style and roles are preserved. You can now return to Discord.</p>
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
