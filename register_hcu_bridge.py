import httpx
import json
import asyncio
import sys

# --- STATIC CONFIGURATION ---
HCU_IP = "192.168.178.118"
PLUGIN_ID = "de.community.fastapi.bridge"

async def get_proper_token():
    # Ask for the key on the terminal
    print("\n" + "="*40)
    user_key = input("🔑 Enter 6-digit Activation Key from HCU UI: ").strip().upper()
    print("="*40 + "\n")

    if len(user_key) != 6:
        print("❌ Error: Activation keys must be exactly 6 characters.")
        return

    auth_url = f"https://{HCU_IP}:6969"
    headers = {"VERSION": "12", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient(verify=False) as client:
        print(f"📡 Step 1: Requesting Auth Token for '{PLUGIN_ID}'...")
        
        req_body = {
            "activationKey": user_key,
            "pluginId": PLUGIN_ID,
            "friendlyName": {"en": "FastAPI Bridge", "de": "FastAPI Bridge"}
        }
        
        try:
            resp1 = await client.post(
                f"{auth_url}/hmip/auth/requestConnectApiAuthToken", 
                headers=headers, 
                json=req_body, 
                timeout=10
            )
            
            if resp1.status_code != 200:
                print(f"❌ Step 1 Failed ({resp1.status_code}): {resp1.text}")
                return

            token = resp1.json().get("authToken")
            print(f"✅ Step 1 Success! Temporary Token received.")

            print("📡 Step 2: Confirming Auth Token with HCU...")
            confirm_body = {
                "activationKey": user_key,
                "authToken": token
            }
            
            resp2 = await client.post(
                f"{auth_url}/hmip/auth/confirmConnectApiAuthToken", 
                headers=headers, 
                json=confirm_body, 
                timeout=10
            )

            if resp2.status_code == 200:
                print("\n" + "🎉" * 20)
                print("SUCCESS! YOUR PERMANENT TOKEN IS:")
                print(f"\n{token}\n")
                print("🎉" * 20)
                print("\nUpdate your homematic_sensors.py with this token.")
            else:
                print(f"❌ Step 2 Failed ({resp2.status_code}): {resp2.text}")

        except Exception as e:
            print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(get_proper_token())
    except KeyboardInterrupt:
        print("\n👋 Cancelled.")
        sys.exit(0)