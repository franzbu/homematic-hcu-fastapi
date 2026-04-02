# Homematic HCU FastAPI Bridge

While the CCU3 can natively detach relay switching from physical button presses, the **Homematic IP HCU (Home Control Unit)** lacks this functionality out of the box. 

This **FastAPI plugin** restores that missing flexibility. By acting as a bridge, it allows you to detach physical buttons from their default actions and assign them to any event—whether they are HCU-internal or entirely external.

<img width="578" height="562" alt="Screenshot 2026-04-02 at 2 24 10 PM" src="https://github.com/user-attachments/assets/f33fb262-79fd-467b-b2f4-38f45ba730b0" />

## 🚀 Key Features

* **Precision Control:** Instead of the rather imprecise default dimming on the HmIP-BDT, you can configure short-presses to increment/decrement brightness by specific percentages.
* **Multi-Tap Support:** Assign actions to double-presses (e.g., +/- 10% brightness) or long-presses (e.g., jump to a predefined scene).
* **Home Assistant Integration:** Trigger any Home Assistant script via your Homematic buttons (e.g., double long-press to lock the front door).
* **Detached Relays:** Use the internal relay of a HmIP-BSM as a pure output device that only triggers under specific conditions, completely independent of the physical buttons.

---

## 🛠 Installation & Setup

### 1. Requirements
* **Environment:** Virtually any Linux environment (runs perfectly in a lightweight Proxmox LXC container).
* **Registration:** Run `register_hcu_bridge.py` to register the FastAPI bridge with your HCU. Once successful, the plugin will appear in your interface.

<img width="1015" height="657" alt="HCU Plugin Interface" src="https://github.com/user-attachments/assets/6569d2c0-cbe3-4851-b267-f45e4e9e1b83" />

### 2. Detaching Buttons
To take full control, you must first "silence" the default Homematic behavior:
1.  **Disable** the default actions in the Homematic IP app.
2.  **Create Dummy Automations** for the disabled buttons. You typically need four per device (Short/Long press for both Button 1 and Button 2).
3.  **Action:** These automations can trigger any meaningless action. For a cleaner setup, use the [Dummy Switch Plugin](https://homematic-forum.de/forum/viewtopic.php?t=86903).

#### Setup Examples:
<p align="center">
  <img width="300" src="https://github.com/user-attachments/assets/1a1277c1-685e-4de8-b3a0-be8bf75c5ca9" />
  <img width="300" src="https://github.com/user-attachments/assets/1a1277c1-685e-4de8-b3a0-be8bf75c5ca9" />
  <img width="300" src="https://github.com/user-attachments/assets/a1e59de0-68b5-44e2-839a-db06cdc391ce" />
</p>

### 3. Intercepting IDs
After creating your dummy automations, use the `hcu_sniffer.py` tool to identify the specific Homematic Automation IDs. You will then enter these IDs into your configuration to map them to custom logic.

<img width="806" height="739" alt="HCU Sniffer Tool" src="https://github.com/user-attachments/assets/085d2a27-5eea-4efc-a8de-64689310b7f7" />

---

## 🧠 System Architecture

### What the FastAPI bridge does
It acts as a **real-time bridge** between Homematic (HCU), Home Assistant, and ESP devices, providing a unified API layer on top.

### ⚙️ Core Responsibilities
1.  **🔌 HCU Connectivity:** Opens a persistent WebSocket connection to subscribe to device state changes (dimmers, relays, sensors) and button/rule events.
2.  **🧩 Event Processing:** Maps raw UUID events to logical actions (e.g., `blueroom_bdt_btn1_short`), tracks multi-click sequences, and executes rules (dimming, toggling, or HA triggers).
3.  **🏠 Home Assistant Integration:** Calls the HA REST API to trigger scripts based on Homematic physical inputs.
4.  **🌡️ Sensor Forwarding:** Forwards temperature and humidity data from Homematic to ESP devices via HTTP.
5.  **📊 State Management:** Maintains an internal state of all dimmer levels, relay states, and sensor values to keep everything in sync with the HCU.
6.  **🌐 Minimal API:** Exposes an `/api/status` endpoint via Uvicorn to monitor the current system state.

---

### 🧩 In short
**It’s an event-driven automation engine and protocol bridge that gives you total control over your Homematic IP hardware.**
