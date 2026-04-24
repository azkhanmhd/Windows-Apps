# 💬 MC Chat Overlay

A lightweight Windows desktop app that displays your Minecraft chat in real-time as an on-screen overlay.

Built using Python + Tkinter, this tool reads your Minecraft log file and shows chat messages directly on your screen while you play.

Vibecode

---

## 🚀 Key Features

* **Real-Time Chat Overlay** – Instantly shows in-game chat without opening chat menu  
* **Custom Position & Size** – Move and resize anywhere on your screen  
* **Click-Through Mode** – Lock the overlay so it doesn’t block your gameplay  
* **Full Appearance Control** – Change font size, colors, outline, and opacity  
* **Live Log Monitoring** – Automatically reads Minecraft log file continuously  
* **System Tray Support** – Run quietly in the background and control anytime  
* **Message Limit Control** – Choose how many messages stay visible  

---

## 📥 Download

Grab the setup here:

https://drive.google.com/file/d/1w4uC21a8F9IzTD45QaLaBa7A64Vx8Slw/view?usp=sharing

> No need to install Python. Just run the `.exe` and you're good.

---

## 🛠️ How to Use

Open the app and it will automatically try to detect your Minecraft log file  

If it doesn’t show chat, go to settings and select:
.minecraft/logs/latest.log

Adjust position, size, colors, and opacity from the settings window  

Turn on **Lock (click-through)** if you want it to stay on screen without blocking clicks  

Minimize to tray and let it run while you play  

---

## ⚙️ How It Works

The app reads your Minecraft log file in real time and extracts chat messages from lines containing `[CHAT]`.  

It then renders them in a transparent, always-on-top overlay window.

---

## 🔒 Security Notice

Since this is a custom-built `.exe` compiled from Python, Windows may flag it as "Unknown".  

That’s normal for unsigned apps — you can safely run it.

---

> Made With ❤️&☕ By Azk 💗
