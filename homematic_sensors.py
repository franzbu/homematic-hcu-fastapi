# Service Name: homematic-bridge.service
# HCU Plugin Name: FastAPI Bridge
# Script Name: homematic_sensors.py
# Version: Release 2026-03-29

import asyncio
import json
import logging
import ssl
import time
from urllib.parse import quote
from fastapi import FastAPI
from contextlib import asynccontextmanager
import websockets
import httpx
import uvicorn

# --- CONFIGURATION ---
HCU_HOST = "192.168.178.118"
AUTH_TOKEN = "00026444DD55D6F59F2F04908A615C2ADF64529BDA2E29865159551DAB898D8C878"
PLUGIN_ID = "de.community.fastapi.bridge"
ESP_IP = "192.168.178.32"

HA_URL = "http://192.168.178.23:8123"
HA_TOKEN = "aaaeyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIzOTFkNjFmNzQ5ZWU0MWNlYjZhNWQ4NGJjZTFiNzdhYyIsImlhdCI6MTc3NDY5MDA1NSwiZXhwIjoyMDkwMDUwMDU1fQ.6rAF_9ZP1bv-3CzncyG08yhE-eYGrslC3ylRQX0c-_A"

# --- HARDWARE REGISTRY ---
DEVICES = {
    # --- Dimmers (BDT) ---
    "blueroom_bdt": "3014F711A00008E4098DDF51",
    "bedroom_bdt": "3014F711A00008E409944C0A",
    "livingroom_bdt": "3014F711A00008E0C992BD3E",

    # --- Relays (BSM) ---
    "blueroom_bsm": "3014F711A0000864098F2C93", 
    "livingroom_bsm": "3014F711A0000864098C1169",
    "lr_east_bsm": "3014F711A0000864098C11F4",
}

# Derived automatically to maintain API backward compatibility
DIMMERS = [v for k, v in DEVICES.items() if k.endswith("_bdt")]
RELAYS = [v for k, v in DEVICES.items() if k.endswith("_bsm")]

# sensors that are pushed to ESP (Froeling)
SENSORS = {"greenhouse": "3014F711A00010DF29924792", "outdoor": "3014F711A00010DD89B3AD37", "stubbe": "3014F711A0000CA0C9A7464A", "troge": "3014F711A00010DF29924293"}

# --- RULE MAPPINGS (THE CONTROL PANEL) ---

# Emptied to prevent the Blue Room relay from double-toggling
LOCAL_RELAY_RULES = {}

# actuators that trigger events either in HA or HCU
UUID_MAP = {
    # --- Blue Room BDT (DF51) ---
    "43af8376-86fa-42c7-af41-9df4a1da7353": "blueroom_bdt_btn2_short",  # Blue Room BDT: btn2 (up), short
    "60286a6d-28cf-446f-90eb-5176054f54cb": "blueroom_bdt_btn2_long",   # Blue Room BDT: btn2 (up), long
    "f7849b49-0754-4544-ac92-92721a8f6383": "blueroom_bdt_btn1_short",  # Blue Room BDT: btn1 (down), short
    "6e05f0cf-a49e-4828-a482-a0c638590dad": "blueroom_bdt_btn1_long",   # Blue Room BDT: btn1 (down), long

    # --- Blue Room BSM (2C93) ---
    "f0587ad6-5a87-42fe-af52-706f918c34b7": "blueroom_bsm_btn1_short",  # Blue Room BSM: btn1 (down), short
    "fa88eeb5-f681-4ca4-8dc4-5195069c5986": "blueroom_bsm_btn1_long",   # Blue Room BSM: btn1 (down), long
    "37945faf-1a1b-4a88-9c1f-deffeef84c13": "blueroom_bsm_btn2_short",  # Blue Room BSM: btn2 (up), short
    "836ea4e2-571e-4e5c-bb36-802efb20b6ea": "blueroom_bsm_btn2_long",   # Blue Room BSM: btn2 (up), long

    # --- Bedroom BDT (4C0A) ---
    "ede983c7-54fb-4567-817e-2ea180c35508": "bedroom_bdt_btn2_short",   # Bedroom BDT: btn2 (up), short
    "5b6d5b50-493c-46b6-abe3-0424462ecb93": "bedroom_bdt_btn2_long",    # Bedroom BDT: btn2 (up), long
    "084ebc6f-3b0a-483b-934c-19c1fa54b0ac": "bedroom_bdt_btn1_short",   # Bedroom BDT: btn1 (down), short
    "d5480a25-3700-4ca6-b3c0-6b7785ef9231": "bedroom_bdt_btn1_long",    # Bedroom BDT: btn1 (down), long

    # --- Livingroom BDT (BD3E) ---
    "8843f20a-58d2-4474-a575-4918b22b8510": "livingroom_bdt_btn2_short", # Living Room BDT: btn2 (up), short
    "6afe420e-baf6-4552-ae69-abe2ee827e29": "livingroom_bdt_btn2_long",  # Living Room BDT: btn2 (up), long
    "029b70d1-c89d-438f-807d-414427c2b8c0": "livingroom_bdt_btn1_short", # Living Room BDT: btn1 (down), short
    "2ea0e799-1d06-4ff4-9d09-a5e550b207af": "livingroom_bdt_btn1_long",  # Living Room BDT: btn1 (down), long

    # --- Living Room BSM (1169) ---
    "239ec689-8bf6-45b6-8c53-735ec03dde8a": "livingroom_bsm_btn1_short", # Living Room BSM: btn1 (down), short
    "9c39f159-3e2d-4c4d-9e2d-9e87dabdc971": "livingroom_bsm_btn1_long",  # Living Room BSM: btn1 (down), long
    "6c4f9a16-fe83-4a2d-8dcc-41f1d7121e52": "livingroom_bsm_btn2_short", # Living Room BSM: btn2 (up), short
    "0a41e1d3-b792-409b-8861-13aea97ecae3": "livingroom_bsm_btn2_long",  # Living Room BSM: btn2 (up), long

    # --- Living Room East BSM (11F4) ---
    "3172b1b3-35b7-4c23-8091-4d321e8f25b6": "lr_east_bsm_btn1_short",    # LR East BSM: btn1 (down), short
    "dc0d9262-c202-4a25-beb4-924711ad1e0d": "lr_east_bsm_btn1_long",     # LR East BSM: btn1 (down), long
    "253c7d0b-3484-4bb4-81fa-47414785a3fc": "lr_east_bsm_btn2_short",    # LR East BSM: btn2 (up), short
    "b4900dfd-b81d-4398-beac-cf2d988e54e8": "lr_east_bsm_btn2_long",     # LR East BSM: btn2 (up), long
}

# --- DEVICE RULES (THE LOGIC MATRIX) ---
DEVICE_RULES = {
    # --- Blue Room BDT (DF51) ---
    "blueroom_bdt_btn1_short": {"action": "step", "val": -0.01},
    "blueroom_bdt_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0}, # switch off (0.00) fading light out within 1.0 seconds 
    "blueroom_bdt_btn1_short_short": {"action": "step", "val": -0.05},
    "blueroom_bdt_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0},
    "blueroom_bdt_btn2_short": {"action": "step", "val": 0.01},
    "blueroom_bdt_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0},
    "blueroom_bdt_btn2_short_short": {"action": "step", "val": 0.05},
    "blueroom_bdt_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0},

    # --- Blue Room BSM (2C93) ---
    "blueroom_bsm_btn1_short": {"script_name": "hmip1_btn1_short"},
    "blueroom_bsm_btn1_long": {"script_name": "hmip1_btn1_long"},
    "blueroom_bsm_btn1_short_short": {"script_name": "hmip1_btn1_short_short"},
    "blueroom_bsm_btn1_short_long": {"script_name": "hmip1_btn1_short_long"},
    "blueroom_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "blueroom_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    #"blueroom_bsm_btn2_short": {"action": "toggle"},
    "blueroom_bsm_btn2_short": {"script_name": "hmip2_btn2_short"},
    "blueroom_bsm_btn2_long": {"script_name": "hmip1_btn2_long"},
    "blueroom_bsm_btn2_short_short": {"script_name": "hmip1_btn2_short_short"},
    "blueroom_bsm_btn2_short_long": {"script_name": "hmip1_btn2_short_long"},
    "blueroom_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "blueroom_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Bedroom BDT (4C0A) ---
    "bedroom_bdt_btn1_short": {"action": "step", "val": -0.01},
    "bedroom_bdt_btn1_long": {"action": "level", "val": 0.00, "ramp": 0.0},
    "bedroom_bdt_btn1_short_short": {"action": "step", "val": -0.05},
    "bedroom_bdt_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 0.0},
    "bedroom_bdt_btn2_short": {"action": "step", "val": 0.01},
    "bedroom_bdt_btn2_long": {"action": "level", "val": 0.4, "ramp": 0.0},
    "bedroom_bdt_btn2_short_short": {"action": "step", "val": 0.05},
    "bedroom_bdt_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 0.0},
    
    # --- Livingroom BDT (BD3E) ---
    "livingroom_bdt_btn1_short": {"action": "step", "val": -0.01},
    "livingroom_bdt_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0}, # switch off (0.00) fading light out within 1.0 seconds 
    "livingroom_bdt_btn1_short_short": {"action": "step", "val": -0.05},
    "livingroom_bdt_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0},
    "livingroom_bdt_btn2_short": {"action": "step", "val": 0.01},
    "livingroom_bdt_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0},
    "livingroom_bdt_btn2_short_short": {"action": "step", "val": 0.05},
    "livingroom_bdt_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0},

    # --- Living Room BSM (1169) ---
    "livingroom_bsm_btn1_short": {"script_name": "hmip1_btn1_short"},
    "livingroom_bsm_btn1_long": {"script_name": "hmip1_btn1_long"},
    "livingroom_bsm_btn1_short_short": {"script_name": "hmip1_btn1_short_short"},
    "livingroom_bsm_btn1_short_long": {"script_name": "hmip1_btn1_short_long"},
    "livingroom_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "livingroom_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "livingroom_bsm_btn2_short": {"script_name": "hmip1_btn2_short"},
    "livingroom_bsm_btn2_long": {"script_name": "hmip1_btn2_long"},
    "livingroom_bsm_btn2_short_short": {"script_name": "hmip1_btn2_short_short"},
    "livingroom_bsm_btn2_short_long": {"script_name": "hmip1_btn2_short_long"},
    "livingroom_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "livingroom_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Living Room East BSM (11F4) ---
    "lr_east_bsm_btn1_short": {"script_name": "hmip1_btn1_short"},
    "lr_east_bsm_btn1_long": {"script_name": "hmip1_btn1_long"},
    "lr_east_bsm_btn1_short_short": {"script_name": "hmip1_btn1_short_short"},
    "lr_east_bsm_btn1_short_long": {"script_name": "hmip1_btn1_short_long"},
    "lr_east_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "lr_east_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "lr_east_bsm_btn2_short": {"script_name": "hmip2_btn2_short"},
    "lr_east_bsm_btn2_long": {"script_name": "hmip1_btn2_long"},
    "lr_east_bsm_btn2_short_short": {"script_name": "hmip1_btn2_short_short"},
    "lr_east_bsm_btn2_short_long": {"script_name": "hmip1_btn2_short_long"},
    "lr_east_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "lr_east_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},
}

# --- STATE ---
ALL_RULE_IDS = list(UUID_MAP.keys()) + list(LOCAL_RELAY_RULES.keys())
APP_STATE = {
    "dimmers": {did: {"level": 0.0} for did in DIMMERS},
    "relays": {rid: {"on": False} for rid in RELAYS},
    "rules": {rid: {"ts": 0, "cnt": 0} for rid in ALL_RULE_IDS},
    "sequence_tracker": {},
    "initialized": False,
    "greenhouse": {"temp": None, "hum": None}, "outdoor": {"temp": None, "hum": None},
    "stubbe": {"temp": None, "hum": None}, "troge": {"temp": None, "hum": None}
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("homematic-bridge")
http_client: httpx.AsyncClient = None

# --- LOCAL HCU CONTROL LOGIC ---

async def set_dimmer_level(websocket, dimmer_id: str, level: float, ramp_time: float = 0.0):
    # Dimmer floor constraint: Stop at 0% safely
    level = max(0.00, min(1.0, round(level, 2)))
    logger.info(f"💡 Target Dimmer ({dimmer_id[-4:]}) Level: {int(level * 100)}% (Ramp: {ramp_time}s)")
    APP_STATE["dimmers"][dimmer_id]["level"] = level
    path = "/hmip/device/control/setDimLevel"
    body = {"deviceId": dimmer_id, "channelIndex": 1, "dimLevel": float(level)}
    if ramp_time > 0:
        path = "/hmip/device/control/setDimLevelWithTime"
        body["rampTime"] = float(ramp_time)
    cmd = {"type": "HMIP_SYSTEM_REQUEST", "id": str(int(time.time())), "pluginId": PLUGIN_ID, "body": {"path": path, "body": body}}
    await websocket.send(json.dumps(cmd))

async def toggle_hcu_relay(websocket, device_id: str):
    new_state = not APP_STATE["relays"][device_id]["on"]
    logger.info(f"🔌 Toggling HCU Relay ({device_id[-4:]}) -> {'ON' if new_state else 'OFF'}")
    cmd = {"type": "HMIP_SYSTEM_REQUEST", "id": str(int(time.time())), "pluginId": PLUGIN_ID, "body": {"path": "/hmip/device/control/setSwitchState", "body": {"deviceId": device_id, "channelIndex": 1, "on": new_state}}}
    await websocket.send(json.dumps(cmd))

# --- HOME ASSISTANT LOGIC ---
async def trigger_ha_script(script_name: str):
    global http_client
    # Change the endpoint to the universal 'turn_on' service
    url = f"{HA_URL.rstrip('/')}/api/services/script/turn_on"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}", 
        "Content-Type": "application/json"
    }
    # Pass the entity_id in the JSON payload
    payload = {"entity_id": f"script.{script_name}"}
    
    try: 
        logger.info(f"🚀 Triggering HA Script: {script_name}")
        response = await http_client.post(url, headers=headers, json=payload, timeout=2.0)
        
        # Log the exact error from HA if it fails again
        if response.status_code != 200:
            logger.error(f"HA rejected request ({response.status_code}): {response.text}")
    except Exception as e:
        logger.error(f"HA Connection Error: {e}")

async def push_to_esp(sensor_name: str, temp: float, hum: int):
    global http_client
    try:
        name_cap = sensor_name.capitalize()
        if temp is not None: await http_client.post(f"http://{ESP_IP}/number/{quote(f'RX Temp {name_cap}')}/set?value={temp}", content="", timeout=2.0)
        if hum is not None: await http_client.post(f"http://{ESP_IP}/number/{quote(f'RX Hum {name_cap}')}/set?value={hum}", content="", timeout=2.0)
    except Exception: pass

# --- SEQUENCE TRACKER LOGIC ---
async def process_button_press(websocket, action_key: str):
    # Split action_key (e.g., "blueroom_bdt_btn1_short") into base and press type
    tracker_key, press_type = action_key.rsplit('_', 1)
    
    if tracker_key not in APP_STATE["sequence_tracker"]:
        APP_STATE["sequence_tracker"][tracker_key] = {"sequence": [], "task": None}
        
    tracker = APP_STATE["sequence_tracker"][tracker_key]
    
    # Deduplicate continuous "long" bursts from holding the button
    if press_type == "long" and tracker["sequence"] and tracker["sequence"][-1] == "long":
        return

    tracker["sequence"].append(press_type)
    
    if tracker["task"] and not tracker["task"].done():
        tracker["task"].cancel()

    # The actual execution logic broken into its own inner function
    async def _execute_sequence():
        raw_seq = tracker["sequence"]
        seq_string = "_".join(raw_seq)
        rule_key = f"{tracker_key}_{seq_string}"
        
        rule = DEVICE_RULES.get(rule_key)
        if rule:
            if "script_name" in rule:
                await trigger_ha_script(rule["script_name"])
            elif "action" in rule:
                device_name = tracker_key.rsplit('_', 1)[0] # Extracts "blueroom_bdt" from "blueroom_bdt_btn1"
                dev_id = DEVICES.get(device_name)
                
                if device_name.endswith("_bdt"):
                    if rule["action"] == "step":
                        curr = APP_STATE["dimmers"][dev_id]["level"]
                        await set_dimmer_level(websocket, dev_id, curr + rule["val"])
                    elif rule["action"] == "level":
                        await set_dimmer_level(websocket, dev_id, rule["val"], rule.get("ramp", 0.0))
                elif device_name.endswith("_bsm"):
                    if rule["action"] == "toggle":
                        await toggle_hcu_relay(websocket, dev_id)
        else:
            logger.info(f"⚠️ No action defined for {rule_key}")

        # Reset the tracker so it's ready for the next button interaction
        tracker["sequence"], tracker["task"] = [], None

    # THE NEW OPTIMIZATION:
    # If we have reached 2 clicks (our maximum sequence length), execute INSTANTLY.
    if len(tracker["sequence"]) >= 2:
        await _execute_sequence()
    else:
        # If it's only 1 click, wait exactly 0.4s to see if a second click comes.
        async def _sequence_timer():
            await asyncio.sleep(0.6) 
            await _execute_sequence()
            
        tracker["task"] = asyncio.create_task(_sequence_timer())

# --- WEBSOCKET LISTENER ---
async def hcu_listener():
    uri = f"wss://{HCU_HOST}:9001"
    headers = {"authtoken": AUTH_TOKEN, "plugin-id": PLUGIN_ID, "hmip-system-events": "true"}
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname, ssl_context.verify_mode = False, ssl.CERT_NONE
    
    while True:
        try:
            async with websockets.connect(uri, additional_headers=headers, ssl=ssl_context) as websocket:
                logger.info("✅ Connected to HCU!")
                await websocket.send(json.dumps({"type": "HMIP_SYSTEM_REQUEST", "id": "init", "pluginId": PLUGIN_ID, "body": {"path": "/hmip/home/getSystemState", "body": {}}}))
                
                async for message in websocket:
                    msg = json.loads(message)
                    m_type, m_id = msg.get("type"), msg.get("id")
                    
                    if m_type == "PLUGIN_STATE_REQUEST":
                        await websocket.send(json.dumps({"id": m_id, "pluginId": PLUGIN_ID, "type": "PLUGIN_STATE_RESPONSE", "body": {"pluginReadinessStatus": "READY"}}))
                    elif m_type == "HMIP_SYSTEM_RESPONSE" and m_id == "init":
                        body = msg.get("body", {}).get("body", {})
                        devs = body.get("devices", {})
                        for d_id in DIMMERS:
                            if d_id in devs:
                                for ch in devs[d_id].get("functionalChannels", {}).values():
                                    if "dimLevel" in ch: APP_STATE["dimmers"][d_id]["level"] = ch["dimLevel"]
                        for r_id in RELAYS:
                            if r_id in devs:
                                for ch in devs[r_id].get("functionalChannels", {}).values():
                                    if "on" in ch: APP_STATE["relays"][r_id]["on"] = ch["on"]
                        rules = body.get("home", {}).get("ruleMetaDatas", {})
                        for rid in APP_STATE["rules"]:
                            if rid in rules:
                                APP_STATE["rules"][rid]["ts"] = rules[rid].get("lastExecutionTimestamp") or 0
                                APP_STATE["rules"][rid]["cnt"] = rules[rid].get("executionCounterOfDay") or 0
                        APP_STATE["initialized"] = True
                        
                    elif m_type == "HMIP_SYSTEM_EVENT":
                        events = msg.get("body", {}).get("eventTransaction", {}).get("events", {})
                        for e in events.values():
                            if e.get("pushEventType") == "DEVICE_CHANGED":
                                dev, d_id = e.get("device", {}), e.get("device", {}).get("id")
                                if d_id in DIMMERS:
                                    for ch in dev.get("functionalChannels", {}).values():
                                        if "dimLevel" in ch: APP_STATE["dimmers"][d_id]["level"] = ch["dimLevel"]
                                elif d_id in RELAYS:
                                    for ch in dev.get("functionalChannels", {}).values():
                                        if "on" in ch: APP_STATE["relays"][d_id]["on"] = ch["on"]
                                name = next((n for n, s in SENSORS.items() if s == d_id), None)
                                if name:
                                    for ch in dev.get("functionalChannels", {}).values():
                                        t, h = ch.get("actualTemperature"), ch.get("humidity")
                                        if t is not None or h is not None:
                                            APP_STATE[name]["temp"], APP_STATE[name]["hum"] = t, h
                                            await push_to_esp(name, t, h)
                                            
                            elif e.get("pushEventType") == "HOME_CHANGED" and APP_STATE["initialized"]:
                                rules = e.get("home", {}).get("ruleMetaDatas", {})
                                for rid, rdata in rules.items():
                                    if rid not in APP_STATE["rules"]: continue
                                    new_ts, new_cnt = rdata.get("lastExecutionTimestamp") or 0, rdata.get("executionCounterOfDay") or 0
                                    if new_ts > APP_STATE["rules"][rid]["ts"] or new_cnt > APP_STATE["rules"][rid]["cnt"]:
                                        APP_STATE["rules"][rid]["ts"], APP_STATE["rules"][rid]["cnt"] = new_ts, new_cnt
                                        
                                        if rid in LOCAL_RELAY_RULES:
                                            await toggle_hcu_relay(websocket, LOCAL_RELAY_RULES[rid])
                                        
                                        if rid in UUID_MAP:
                                            action_key = UUID_MAP[rid]
                                            await process_button_press(websocket, action_key)
                                            
        except Exception as e:
            logger.error(f"WS Error: {e}. Retrying in 10s..."); await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, hcu_task
    http_client, hcu_task = httpx.AsyncClient(), asyncio.create_task(hcu_listener())
    yield
    hcu_task.cancel(); await http_client.aclose()

app = FastAPI(lifespan=lifespan)
@app.get("/api/status")
async def get_status(): return {"bridge_status": "active", "current_state": APP_STATE}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)