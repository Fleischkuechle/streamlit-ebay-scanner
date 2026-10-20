import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
from PIL import Image, ImageOps
import io
import base64
import urllib.parse
import re
import json
import os
from datetime import datetime

# ==========================================
# KONFIGURATION AUS STREAMLIT SECRETS
# ==========================================
if "GROQ_API_KEY" not in st.secrets:
    st.error("❌ Kein GROQ_API_KEY in .streamlit/secrets.toml gefunden!")
    st.stop()

GROQ_API_KEY = st.secrets["GROQ_API_KEY"].strip()
HISTORY_FILE = "history.json"

st.set_page_config(
    page_title="eBay Sold Price Checker", page_icon="📦", layout="centered"
)
st.title("📦 eBay Sold Price Scanner")


# ==========================================
# HISTORIE-VERWALTUNG (inkl. Mini-Thumbnails)
# ==========================================
def load_history():
    """Lädt die Historie aus der lokalen JSON-Datei."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def create_thumbnail_b64(raw_bytes, max_dim=120) -> str:
    """Erstellt ein winziges Thumbnail (ca. 2-3 KB) als Base64-String."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=65)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return ""


def add_to_history(query, url, thumb_b64=""):
    """Fügt einen neuen Eintrag inklusive Bild-Thumbnail zur Historie hinzu."""
    history = load_history()
    # Duplikate ganz oben vermeiden
    if history and history[0].get("query") == query:
        return
    new_entry = {
        "query": query,
        "url": url,
        "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "thumb": thumb_b64,
    }
    history.insert(0, new_entry)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ==========================================
# BILD- & KI-FUNKTIONEN
# ==========================================
def optimize_image_bytes(raw_bytes, max_dimension=800) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_dimension, max_dimension))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def identify_product_groq(image_bytes: bytes, status_box):
    client = Groq(api_key=GROQ_API_KEY)
    status_box.update(label="🤖 Analysiere Foto mit Groq (Qwen 3.8)...")
    status_box.write("🚀 Sende Bild an Groq...")

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Identifiziere das Produkt auf diesem Foto präzise für eine eBay-Suche. "
        "Gib NUR 3 bis 6 treffende Suchbegriffe aus (z.B. Titel, Edition, Format wie DVD/Box). "
        "Keine Sätze, keine Artikel, keine Anführungszeichen, keine Klammern."
    )

    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                    },
                ],
            }
        ],
        max_tokens=40,
    )

    result = response.choices[0].message.content or ""
    return re.sub(r"[\(\)'\"]", "", result).strip()


# ==========================================
# KAMERA-BEREICH
# ==========================================
img_file = st.camera_input("📸 Mache ein Foto vom Artikel:")

if img_file:
    raw_img_bytes = img_file.getvalue()
    compressed_bytes = optimize_image_bytes(raw_img_bytes)

    # Nur ausführen, wenn ein neues Foto gemacht wurde
    if (
        "detected_query" not in st.session_state
        or st.session_state.get("last_img") != img_file.file_id
    ):
        st.session_state["last_img"] = img_file.file_id

        with st.status("🤖 KI startet Erkennung...", expanded=True) as status:
            try:
                query_text = identify_product_groq(compressed_bytes, status_box=status)
                st.session_state["detected_query"] = query_text
                status.update(
                    label=f"✅ Erkannt: {query_text}",
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                status.update(label="❌ Erkennung fehlgeschlagen", state="error")
                st.error(f"Fehler: {e}")
                st.session_state["detected_query"] = ""

    current_query = st.text_input(
        "Suchbegriff anpassen (optional):",
        value=st.session_state.get("detected_query", ""),
    )

    if current_query:
        clean_query = re.sub(r"[^\w\s\-]", "", current_query).strip()
        encoded_query = urllib.parse.quote(clean_query)
        ebay_url = f"https://www.ebay.de/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_sop=13"

        # Miniatur-Bild für die Historie generieren und abspeichern
        thumb_b64 = create_thumbnail_b64(raw_img_bytes)
        add_to_history(clean_query, ebay_url, thumb_b64=thumb_b64)

        st.success(f"Bereit für eBay: **{clean_query}**")

        # 1. Automatisches Öffnen im Browser (einmalig pro Scan)
        if st.session_state.get("auto_opened_url") != ebay_url:
            st.session_state["auto_opened_url"] = ebay_url
            components.html(
                f"""
                <script>
                    window.open('{ebay_url}', '_blank');
                </script>
                """,
                height=0,
                width=0,
            )

        # 2. Buttons nebeneinander: Auf eBay öffnen + Link kopieren
        col1, col2 = st.columns([1, 1])
        with col1:
            st.link_button(
                "👉 Auf eBay öffnen",
                ebay_url,
                type="primary",
                use_container_width=True,
            )

        with col2:
            copy_html = f"""
            <button onclick="
                const btn = this;
                navigator.clipboard.writeText('{ebay_url}').then(() => {{
                    const originalText = btn.innerHTML;
                    btn.innerHTML = '✅ Kopiert!';
                    setTimeout(() => btn.innerHTML = originalText, 2000);
                }});
            " style="width: 100%; height: 44px; background-color: #262730; color: white; border: 1px solid #4e5159; border-radius: 8px; font-weight: 600; cursor: pointer;">
                📋 Link kopieren
            </button>
            """
            components.html(copy_html, height=50)

# ==========================================
# GESPEICHERTER VERLAUF (inkl. Thumbnail)
# ==========================================
st.divider()
st.subheader("📜 Gespeicherter Verlauf")

all_history = load_history()

if all_history:
    if "show_all_history" not in st.session_state:
        st.session_state["show_all_history"] = False

    limit = 20
    visible_items = (
        all_history if st.session_state["show_all_history"] else all_history[:limit]
    )

    for item in visible_items:
        # Layout: Links das kleine Bild (1 Teil), Rechts der Button (4 Teile)
        col_img, col_btn = st.columns([1, 4])
        with col_img:
            if item.get("thumb"):
                st.image(
                    f"data:image/jpeg;base64,{item['thumb']}",
                    width=65,
                )
            else:
                st.write("📦")

        with col_btn:
            st.link_button(
                f"🔍 {item['query']} ({item.get('time', '')})",
                item["url"],
                use_container_width=True,
            )

    # Ausklapp-Button, falls mehr als 20 Einträge existieren
    if len(all_history) > limit:
        if not st.session_state["show_all_history"]:
            if st.button(
                f"➕ Mehr anzeigen ({len(all_history) - limit} weitere Einträge)"
            ):
                st.session_state["show_all_history"] = True
                st.rerun()
        else:
            if st.button("➖ Weniger anzeigen (nur letzte 20)"):
                st.session_state["show_all_history"] = False
                st.rerun()
else:
    st.caption("Noch keine Artikel gescannt.")
