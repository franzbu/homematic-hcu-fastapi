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
    "hallway_bdt": "3014F711A00008E0C992BD3E",

    # --- Relays (BSM) ---
    "blueroom_bsm": "3014F711A0000864098F2C93", 
    "lr_east_bsm": "3014F711A0000864098C11F4",
    "hallway_southeast_bsm": "3014F711A0000864098C143F",
    "hallway_southwest_bsm": "3014F711A0000864098C12BD",
    "hallway_northwest_bsm": "3014F711A0000864099E6160",
    "hallway_switchboard_bsm": "3014F711A0000864098C1169",
    "entrance_bsm": "3014F711A0000864098F202F",
}

# Derived automatically to maintain API backward compatibility
DIMMERS = [v for k, v in DEVICES.items() if k.endswith("_bdt")]
RELAYS = [v for k, v in DEVICES.items() if k.endswith("_bsm")]

# sensors that are pushed to the ESP (Froeling)
SENSORS = {
    "greenhouse": "3014F711A00010DF29924792", 
    "outdoor": "3014F711A00010DD89B3AD37", 
    "stubbe": "3014F711A0000CA0C9A7464A", 
    "troge": "3014F711A00010DF29924293",
}

# --- RULE MAPPINGS (THE CONTROL PANEL) ---

# Emptied to prevent the Blue Room relay from double-toggling
LOCAL_RELAY_RULES = {}

# actuators that trigger events either in HA or HCU
UUID_MAP = {
    # --- Blue Room BDT (DF51) ---
    "f7849b49-0754-4544-ac92-92721a8f6383": "blueroom_bdt_btn1_short",  # Blue Room BDT: btn1 (down), short
    "6e05f0cf-a49e-4828-a482-a0c638590dad": "blueroom_bdt_btn1_long",   # Blue Room BDT: btn1 (down), long
    "43af8376-86fa-42c7-af41-9df4a1da7353": "blueroom_bdt_btn2_short",  # Blue Room BDT: btn2 (up), short
    "60286a6d-28cf-446f-90eb-5176054f54cb": "blueroom_bdt_btn2_long",   # Blue Room BDT: btn2 (up), long

    # --- Blue Room BSM (2C93) ---
    "f0587ad6-5a87-42fe-af52-706f918c34b7": "blueroom_bsm_btn1_short",  # Blue Room BSM: btn1 (down), short
    "fa88eeb5-f681-4ca4-8dc4-5195069c5986": "blueroom_bsm_btn1_long",   # Blue Room BSM: btn1 (down), long
    "37945faf-1a1b-4a88-9c1f-deffeef84c13": "blueroom_bsm_btn2_short",  # Blue Room BSM: btn2 (up), short
    "836ea4e2-571e-4e5c-bb36-802efb20b6ea": "blueroom_bsm_btn2_long",   # Blue Room BSM: btn2 (up), long

    # --- Bedroom BDT (4C0A) ---
    "084ebc6f-3b0a-483b-934c-19c1fa54b0ac": "bedroom_bdt_btn1_short",   # Bedroom BDT: btn1 (down), short
    "d5480a25-3700-4ca6-b3c0-6b7785ef9231": "bedroom_bdt_btn1_long",    # Bedroom BDT: btn1 (down), long
    "ede983c7-54fb-4567-817e-2ea180c35508": "bedroom_bdt_btn2_short",   # Bedroom BDT: btn2 (up), short
    "5b6d5b50-493c-46b6-abe3-0424462ecb93": "bedroom_bdt_btn2_long",    # Bedroom BDT: btn2 (up), long


    # --- Hallway BDT (BD3E) ---
    "85ad5816-382a-46b6-84ca-1faa75680f3a": "hallway_bdt_btn1_short", # btn1 (down), short
    "d2cb1fab-9a82-407d-b184-5702aa94dc8f": "hallway_bdt_btn1_long",  # btn1 (down), long
    "b2b85e1f-d9cd-422d-bfd1-9697476f7ab9": "hallway_bdt_btn2_short", # btn2 (up), short
    "4d3f92bd-0afc-453f-9b25-c6df5269aad5": "hallway_bdt_btn2_long",  # btn2 (up), long

    # --- Hallway Southeast BSM (143F) ---
    "8138dc40-23e3-4ff2-a5b2-a8913a88877d": "hallway_southeast_bsm_btn1_short",    # btn1 (down), short
    "ef453c0a-d4d3-4723-8744-54e66ae1e533": "hallway_southeast_bsm_btn1_long",     # btn1 (down), long
    "b572113c-bd4a-4357-a6ce-12b1d79a719a": "hallway_southeast_bsm_btn2_short",    # btn2 (up), short
    "b62b0e33-12ba-43c4-b296-28825309aa8f": "hallway_southeast_bsm_btn2_long",     # btn2 (up), long

    # --- Hallway Southwest BSM (12BD) ---
    "17d0749d-abda-4032-921a-185b96f0e805": "hallway_southwest_bsm_btn1_short",    # btn1 (down), short
    "99c38d7c-43c5-4dca-8602-b71d11ce058d": "hallway_southwest_bsm_btn1_long",     # btn1 (down), long
    "7d955225-e377-40d0-b456-012908462ba5": "hallway_southwest_bsm_btn2_short",    # btn2 (up), short
    "e8fb6a7d-0313-4f73-b1fa-8c781ac88fbb": "hallway_southwest_bsm_btn2_long",     # btn2 (up), long


    # --- Hallway Northwest BSM (6160) ---
    "3172b1b3-35b7-4c23-8091-4d321e8f25b6": "hallway_southwest_bsm_btn1_short",    # btn1 (down), short
    "dc0d9262-c202-4a25-beb4-924711ad1e0d": "hallway_southwest_bsm_btn1_long",     # btn1 (down), long
    "253c7d0b-3484-4bb4-81fa-47414785a3fc": "hallway_southwest_bsm_btn2_short",    # btn2 (up), short
    "b4900dfd-b81d-4398-beac-cf2d988e54e8": "hallway_southwest_bsm_btn2_long",     # btn2 (up), longå

    # --- Hallway Switchboard BSM (1169) ---
    "ab334e1c-7fe7-4079-90f1-800f35ed116c": "hallway_switchboard_bsm_btn1_short",    # btn1 (down), short
    "048a1fbb-0530-4755-bd77-97dfd6ae6da6": "hallway_switchboard_bsm_btn1_long",     # btn1 (down), long
    "9f6a1664-107e-4224-8543-9df1b6f849c0": "hallway_switchboard_bsm_btn2_short",    # btn2 (up), short
    "cdae216d-3402-455e-91c1-845f28037929": "hallway_switchboard_bsm_btn2_long",     # btn2 (up), long

    # --- Entrance BSM (202F) ---
    "ecaae579-c65b-4463-8ca4-cda5e63a82ae": {"device": "entrance_bsm", "button": "btn1", "type": "short"},
    "d42db370-c86f-4ba3-af7d-acea3d5b85e3": {"device": "entrance_bsm", "button": "btn1", "type": "long"},
    "5ce093b0-e138-49d2-a9bb-3fbb28c8569c": {"device": "entrance_bsm", "button": "btn2", "type": "short"},
    "a729897b-f6a1-4994-8b19-68b62e83715d": {"device": "entrance_bsm", "button": "btn2", "type": "long"},
}


# --- DEVICE RULES (THE LOGIC MATRIX) ---
DEVICE_RULES = {
    # --- Blue Room BDT (DF51) ---
    "blueroom_bdt_btn1_short": {"action": "step", "val": -0.01},
    "blueroom_bdt_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0}, # switch off (0.00) fading light out within 1.0 seconds 
    "blueroom_bdt_btn1_short_short": {"action": "step", "val": -0.05},
    "blueroom_bdt_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0},
    "blueroom_bdt_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05},
    "blueroom_bdt_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0},
    "blueroom_bdt_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10},
    "blueroom_bdt_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0},
    # HA scripts: 
    "blueroom_bdt_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "blueroom_bdt_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "blueroom_bdt_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "blueroom_bdt_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},


    # --- Blue Room BSM (2C93) ---
    #"blueroom_bsm_btn2_short": {"action": "toggle"}, # example for toggling the internal relay
    "blueroom_bsm_btn1_short": {"script_name": "hmip1_btn1_short"},
    "blueroom_bsm_btn1_long": {"script_name": "hmip1_btn1_long"},
    "blueroom_bsm_btn1_short_short": {"script_name": "hmip1_btn1_short_short"},
    "blueroom_bsm_btn1_short_long": {"script_name": "hmip1_btn1_short_long"},
    "blueroom_bsm_btn2_short": {"script_name": "hmip2_btn2_short"},
    "blueroom_bsm_btn2_long": {"script_name": "hmip1_btn2_long"},
    "blueroom_bsm_btn2_short_short": {"script_name": "hmip1_btn2_short_short"},
    "blueroom_bsm_btn2_short_long": {"script_name": "hmip1_btn2_short_long"},
    # HA scripts: 
    "blueroom_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "blueroom_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "blueroom_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "blueroom_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Bedroom BDT (4C0A) ---
    # "bedroom_bdt_btn1_short": {"action": "toggle", "id": DEVICES["blueroom_bsm"]}, # example for toggling a bsm relay with another device
    "bedroom_bdt_btn1_short": {"action": "step", "val": -0.01},
    "bedroom_bdt_btn1_long": {"action": "level", "val": 0.00, "ramp": 0.0},
    "bedroom_bdt_btn1_short_short": {"action": "step", "val": -0.05},
    "bedroom_bdt_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 0.0},
    "bedroom_bdt_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05},
    "bedroom_bdt_btn2_long": {"action": "level", "val": 0.4, "ramp": 0.0},
    "bedroom_bdt_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10},
    "bedroom_bdt_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 0.0},
    # HA scripts: 
    "blueroom_bdt_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "blueroom_bdt_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "blueroom_bdt_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "blueroom_bdt_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Living Room BSM (1169) ---
    "livingroom_bsm_btn1_short": {"script_name": "hmip1_btn1_short"},
    "livingroom_bsm_btn1_long": {"script_name": "hmip1_btn1_long"},
    "livingroom_bsm_btn1_short_short": {"script_name": "hmip1_btn1_short_short"},
    "livingroom_bsm_btn1_short_long": {"script_name": "hmip1_btn1_short_long"},
    "livingroom_bsm_btn2_short": {"script_name": "hmip1_btn2_short"},
    "livingroom_bsm_btn2_long": {"script_name": "hmip1_btn2_long"},
    "livingroom_bsm_btn2_short_short": {"script_name": "hmip1_btn2_short_short"},
    "livingroom_bsm_btn2_short_long": {"script_name": "hmip1_btn2_short_long"},
    # HA scripts: 
    "livingroom_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "livingroom_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "livingroom_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "livingroom_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Living Room East BSM (11F4) ---
    "lr_east_bsm_btn1_short": {"script_name": "hmip1_btn1_short"},
    "lr_east_bsm_btn1_long": {"script_name": "hmip1_btn1_long"},
    "lr_east_bsm_btn1_short_short": {"script_name": "hmip1_btn1_short_short"},
    "lr_east_bsm_btn1_short_long": {"script_name": "hmip1_btn1_short_long"},
    "lr_east_bsm_btn2_short": {"script_name": "hmip2_btn2_short"},
    "lr_east_bsm_btn2_long": {"script_name": "hmip1_btn2_long"},
    "lr_east_bsm_btn2_short_short": {"script_name": "hmip1_btn2_short_short"},
    "lr_east_bsm_btn2_short_long": {"script_name": "hmip1_btn2_short_long"},
    # HA scripts: 
    "lr_east_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "lr_east_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "lr_east_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "lr_east_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},


    # --- Hallway BDT (BD3E) ---
    "hallway_bdt_btn1_short": {"action": "step", "val": -0.01},
    "hallway_bdt_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0}, # switch off (0.00) fading light out within 1.0 seconds 
    "hallway_bdt_btn1_short_short": {"action": "step", "val": -0.05},
    "hallway_bdt_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0},
    "hallway_bdt_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05},
    "hallway_bdt_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0},
    "hallway_bdt_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10},
    "hallway_bdt_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0},
    # HA scripts: 
    "hallway_bdt_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "hallway_bdt_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "hallway_bdt_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "hallway_bdt_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},


    # --- Hallway Southeast BSM (143F) ---
    "hallway_southeast_bsm_btn1_short": {"action": "step", "val": -0.01, "id": DEVICES["hallway_bdt"]},
    "hallway_southeast_bsm_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southeast_bsm_btn1_short_short": {"action": "step", "val": -0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southeast_bsm_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southeast_bsm_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southeast_bsm_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southeast_bsm_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10, "id": DEVICES["hallway_bdt"]},
    "hallway_southeast_bsm_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    # HA scripts:
    "hallway_southeast_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "hallway_southeast_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "hallway_southeast_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "hallway_southeast_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Hallway Southwest BSM (12BD) --- 
    "hallway_southwest_bsm_btn1_short": {"action": "step", "val": -0.01, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_short_short": {"action": "step", "val": -0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    # HA scripts:
    "hallway_southwest_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "hallway_southwest_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "hallway_southwest_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "hallway_southwest_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Hallway Northwest BSM (6160) ---
    "hallway_southwest_bsm_btn1_short": {"action": "step", "val": -0.01, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_short_short": {"action": "step", "val": -0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    # HA scripts:
    "hallway_southwest_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "hallway_southwest_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "hallway_southwest_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "hallway_southwest_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Hallway Switchboard BSM (1169) ---
    "hallway_southwest_bsm_btn1_short": {"action": "step", "val": -0.01, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_short_short": {"action": "step", "val": -0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10, "id": DEVICES["hallway_bdt"]},
    "hallway_southwest_bsm_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0, "id": DEVICES["hallway_bdt"]},
    # HA scripts:
    "hallway_southwest_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    "hallway_southwest_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    "hallway_southwest_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    "hallway_southwest_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},

    # --- Entrance BSM (202F) ---
    #"entrance_bsm_btn1_short": {"action": "step", "val": -0.01, "id": "3014F711A00008E4098DDF51"},
    #"entrance_bsm_btn1_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": "3014F711A00008E4098DDF51"},
    #"entrance_bsm_btn1_short_short": {"action": "step", "val": -0.05, "id": "3014F711A00008E4098DDF51"},
    #"entrance_bsm_btn1_short_long": {"action": "level", "val": 0.00, "ramp": 1.0, "id": "3014F711A00008E4098DDF51"},
    #"entrance_bsm_btn2_short": {"action": "step", "val": 0.01, "on_zero": 0.05, "id": "3014F711A00008E4098DDF51"},
    #"entrance_bsm_btn2_long": {"action": "level", "val": 0.4, "ramp": 1.0, "id": "3014F711A00008E4098DDF51"},
    #"entrance_bsm_btn2_short_short": {"action": "step", "val": 0.05, "on_zero": 0.10, "id": "3014F711A00008E4098DDF51"},
    #"entrance_bsm_btn2_short_long": {"action": "level", "val": 0.07, "ramp": 1.0, "id": "3014F711A00008E4098DDF51"},
    # HA scripts:
    #"entrance_bsm_btn1_long_short": {"script_name": "hmip1_btn1_long_short"},
    #"entrance_bsm_btn1_long_long": {"script_name": "hmip1_btn1_long_long"},
    #"entrance_bsm_btn2_long_short": {"script_name": "hmip1_btn2_long_short"},
    #"entrance_bsm_btn2_long_long": {"script_name": "hmip1_btn2_long_long"},
}

# --- STATE ---
ALL_RULE_IDS = list(UUID_MAP.keys()) + list(LOCAL_RELAY_RULES.keys())
APP_STATE = {
    "dimmers": {did: {"level": 0.0} for did in DIMMERS},
    "relays": {rid: {"on": False} for rid in RELAYS},
    "rules": {rid: {"ts": 0, "cnt": 0} for rid in ALL_RULE_IDS},
    "sequence_tracker": {},
    "initialized": False,
}
# Dynamically add all sensors to the state memory
for sensor_name in SENSORS:
    APP_STATE[sensor_name] = {"temp": None, "hum": None}

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
    except Exception as e:
        logger.warning(f"⚠️ Could not push sensor {sensor_name} to ESP: {e}")

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
                # 1. Determine WHICH device to control (Rule ID override or Button's device)
                device_name = tracker_key.rsplit('_', 1)[0]
                target_dev_id = rule.get("id") or DEVICES.get(device_name)
                
                # 2. Determine behavior based on the ACTION requested, not the button's name
                if rule["action"] in ["step", "level"]:
                    # Safely get current dimmer state, defaulting to 0.0 if not yet tracked
                    dimmer_state = APP_STATE["dimmers"].get(target_dev_id, {"level": 0.0})
                    curr = dimmer_state["level"]
                    
                    if rule["action"] == "step":
                        if curr == 0.0 and "on_zero" in rule:
                            target = rule["on_zero"]
                        else:
                            target = curr + rule["val"]
                        await set_dimmer_level(websocket, target_dev_id, target)
                    elif rule["action"] == "level":
                        await set_dimmer_level(websocket, target_dev_id, rule["val"], rule.get("ramp", 0.0))
                        
                elif rule["action"] == "toggle":
                    await toggle_hcu_relay(websocket, target_dev_id)
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
