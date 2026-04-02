import asyncio
import json
import logging
import ssl
import websockets

# --- CONFIGURATION ---
HCU_HOST = "192.168.178.118"
AUTH_TOKEN = "AAA0FE2C97B074ECB1B1CBD0F9E09341C81EEEA7ED6197EDF44B26EF06D40AB0714"

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("hcu-sniffer")

# Tracking timestamps so we only log NEW presses
known_rules = {}

async def sniffer():
    uri = f"wss://{HCU_HOST}:9001"
    headers = {
        "authtoken": AUTH_TOKEN,
        "plugin-id": "de.homeassistant.hcu.integration",
        "hmip-system-events": "true"
    }
    
    # Disable SSL verification for local IP
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    while True:
        try:
            async with websockets.connect(uri, additional_headers=headers, ssl=ssl_context) as ws:
                logger.info("📡 Connected to HCU Sniffer! Press any button now...")

                # 1. Initialize Baseline (get current timestamps)
                await ws.send(json.dumps({
                    "type": "HMIP_SYSTEM_REQUEST",
                    "id": "init_sniffer",
                    "pluginId": "de.homeassistant.hcu.integration",
                    "body": {"path": "/hmip/home/getSystemState", "body": {}}
                }))

                async for message in ws:
                    msg = json.loads(message)

                    # Handle HCU Heartbeat/Readiness
                    if msg.get("type") == "PLUGIN_STATE_REQUEST":
                        await ws.send(json.dumps({
                            "id": msg.get("id"),
                            "pluginId": "de.homeassistant.hcu.integration",
                            "type": "PLUGIN_STATE_RESPONSE",
                            "body": {"pluginReadinessStatus": "READY"}
                        }))
                        continue

                    # Capture initial state
                    if msg.get("type") == "HMIP_SYSTEM_RESPONSE" and msg.get("id") == "init_sniffer":
                        rules = msg.get("body", {}).get("body", {}).get("home", {}).get("ruleMetaDatas", {})
                        for rid, rdata in rules.items():
                            known_rules[rid] = rdata.get("lastExecutionTimestamp") or 0
                        logger.info(f"✅ Baseline set for {len(known_rules)} rules. Listening for clicks...")

                    # 2. Catch Events
                    if msg.get("type") == "HMIP_SYSTEM_EVENT":
                        events = msg.get("body", {}).get("eventTransaction", {}).get("events", {})
                        for e in events.values():
                            if e.get("pushEventType") == "HOME_CHANGED":
                                rules = e.get("home", {}).get("ruleMetaDatas", {})
                                for rid, rdata in rules.items():
                                    new_ts = rdata.get("lastExecutionTimestamp") or 0
                                    old_ts = known_rules.get(rid, 0)

                                    if new_ts > old_ts:
                                        known_rules[rid] = new_ts
                                        label = rdata.get("label", "Unknown Label")
                                        
                                        print("\n" + "="*60)
                                        print(f"🔘 BUTTON CLICK DETECTED!")
                                        print(f"   Label: {label}")
                                        print(f"   ID:    {rid}")
                                        print("="*60 + "\n")

        except Exception as err:
            logger.error(f"Connection lost ({err}). Retrying in 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(sniffer())
    except KeyboardInterrupt:
        print("\nStopping sniffer...")