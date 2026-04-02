# homematic-hcu-fastapi

While the CCU3 can detatch the switching of relays from the actual pressing of the button(s), the Homematic IP's HCU (Home Control Unit) cannot do that out of the box. Since it supports plugins, this missing functionality can be added with this FastAPI plugin, which additionally makes it possible to assign the execution of any event, be it HCU-related or entirely detached from it. 

For example, instead of having to accept the rather imprecise dimming of the HmIP-BDT via long-press of the buttons, short-pressing the buttons can be set to increase and decrease the brightness by any level required; double-pressing can, for example, increase and decrease by 10 percent; long-pressing can go to a predefined level. 

On the other hand, by optionally connecting FastAPI to Home Assistant, it is, for example, possible to lock the front door via double long-press. Another scenario could be to use the internal relay of a HmIP-BSM, which via FastAPI can be detached from the buttons so it does not switch when pressing the buttons (unless wanted), can become an output device, for example, when double long-pressinig one of the buttons, it is (audibly) triggered under pre-defined circumstances. 

Basically there are hardly any limits of what you can do once this FastAPI bridge alongside its HCU plugin is in place.

`register_hcu_bridge.py` needs to be run to register the FastAPI bridge in the HCU; once successfully done, you will see that the plugin has been created.

<img width="1015" height="657" alt="Screenshot 2026-04-02 at 2 05 24 PM" src="https://github.com/user-attachments/assets/6569d2c0-cbe3-4851-b267-f45e4e9e1b83" />

FastAPI can be installed in virtually any linux environment; I have it running withing a lightweight Proxmox LXC Container.

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
