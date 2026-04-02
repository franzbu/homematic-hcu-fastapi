# homematic-hcu-fastapi

🧠 What the FastAPI bridge does
👉 It acts as a real-time bridge between Homematic (HCU), Home Assistant, and an ESP device, with a tiny API on top.

⚙️ Core responsibilities
1. 🔌 Connects to Homematic (HCU)
Opens a persistent WebSocket connection
Subscribes to:
device state changes (dimmers, relays, sensors)
button/rule events

2. 🧩 Processes button events → executes actions
Maps raw UUID events → logical buttons (e.g. blueroom_bdt_btn1_short)
Tracks multi-click sequences (short/long combos)
Executes actions based on rules:
💡 adjust dimmers
🔌 toggle relays
🚀 trigger Home Assistant scripts

3. 🏠 Talks to Home Assistant
Calls HA REST API to trigger scripts
Acts as a bridge between Homematic inputs and HA automations

4. 🌡️ Forwards sensor data to ESP
Receives temperature/humidity from Homematic
Pushes values to ESP via HTTP

5. 🧠 Maintains internal state
Tracks:
dimmer levels
relay states
sensor values
rule execution timestamps
Keeps everything in sync with HCU

6. 🌐 Exposes a minimal API
/api/status → returns current system state
Runs via Uvicorn

🧩 In one sentence
👉 It’s an event-driven automation engine + protocol bridge, with FastAPI just providing a small status endpoint and lifecycle management.
