# 📦 eBay Sold Price Scanner

Eine moderne und mobile-optimierte **Streamlit-Web-App**, die mithilfe von KI (Groq / Qwen Vision) Fotos von Artikeln analysiert, präzise Suchbegriffe für eBay generiert und dich direkt zu den beendeten bzw. verkauften Angeboten (`Sold Items`) auf eBay.de weiterleitet.

---

## ✨ Features

* **🤖 KI-Bilderkennung:** Nutzt Groq und Qwen Vision, um Objekte auf Fotos automatisch zu erkennen und in treffende eBay-Suchbegriffe umzuwandeln[cite: 1, 2].
* **📱 Mobile-First Design:** Für die direkte Nutzung mit dem Smartphone-Fotoapparat optimiert[cite: 2].
* **⚡ Schnellzugriff:** Öffnet die eBay-Suche (gefiltert nach verkauften Artikeln) automatisch im Browser[cite: 1, 2] und bietet einen praktischen Button zum Kopieren des Links.
* **📜 Dauerhafter Verlauf:** Speichert vergangene Suchen lokal in einer JSON-Datei ab, sodass der Verlauf auch nach Neustarts oder einem Foto-Reset erhalten bleibt[cite: 1, 2].

---

## 🛠️ Verwendete Technologien

* **Python**
* **Streamlit** (Web-Framework)
* **Groq API** (für die KI-Bildanalyse)
* **Pillow (PIL)** (Bildverarbeitung & EXIF-Korrektur)

---

## 🚀 Lokale Installation & Start

1. **Repository klonen:**
   ```bash
   git clone [https://github.com/DEIN-BENUTZERNAME/streamlit-ebay-scanner.git](https://github.com/DEIN-BENUTZERNAME/streamlit-ebay-scanner.git)
   cd streamlit-ebay-scanner