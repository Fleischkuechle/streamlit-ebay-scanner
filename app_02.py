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

# ==========================================
# ANDROID PWA META-TAGS (Ermöglicht das Runterwischen)
# ==========================================
st.markdown(
    """
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <style>
        /* Mobile-Optimierung für saubere Darstellung auf Smartphones */
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📦 eBay Sold Price Scanner")


# ==========================================
# HISTORIE-VERWALTUNG (inkl. Thumbnails)
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def create_thumbnail_b64(raw_bytes, max_dim=120) -> str:
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
    history = load_history()
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
# BILD- & KI-FUNKTIONEN (Groq Qwen 3.8)
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
    status_box.update(label="🤖 Analysiere Foto mit Groq...")
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

        thumb_b64 = create_thumbnail_b64(raw_img_bytes)
        add_to_history(clean_query, ebay_url, thumb_b64=thumb_b64)

        st.success(f"Bereit für eBay: **{clean_query}**")

        # ----------------------------------------------------
        # DIESER BUTTON ÖFFNET DAS IN-APP SLIDE-OVER AUF ANDROID
        # ----------------------------------------------------
        st.markdown(
            f"""
            <a href="{ebay_url}" target="_blank" rel="noopener noreferrer" style="text-decoration: none;">
                <button style="
                    width: 100%; 
                    height: 54px; 
                    background: linear-gradient(135deg, #0064d2, #0053b8); 
                    color: white; 
                    border: none; 
                    border-radius: 12px; 
                    font-size: 17px; 
                    font-weight: bold; 
                    cursor: pointer;
                    box-shadow: 0 4px 14px rgba(0, 100, 210, 0.4);
                ">
                    🔍 eBay-Verkäufe ansehen (Slide-Over)
                </button>
            </a>
            """,
            unsafe_allow_html=True,
        )

        st.caption(
            "💡 Tipp: Wische die geöffnete eBay-Seite einfach nach unten weg, um zurück zur Kamera zu kommen."
        )

# ==========================================
# GESPEICHERTER VERLAUF
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
        col_img, col_btn = st.columns([1, 4])
        with col_img:
            if item.get("thumb"):
                st.image(f"data:image/jpeg;base64,{item['thumb']}", width=65)
            else:
                st.write("📦")

        with col_btn:
            # Auch aus dem Verlauf als Slide-Over öffnen
            st.markdown(
                f"""
                <a href="{item['url']}" target="_blank" rel="noopener noreferrer" style="text-decoration: none;">
                    <button style="
                        width: 100%; 
                        height: 42px; 
                        background-color: #262730; 
                        color: white; 
                        border: 1px solid #4e5159; 
                        border-radius: 8px; 
                        font-weight: 500; 
                        text-align: left; 
                        padding-left: 12px;
                        cursor: pointer;
                    ">
                        🔍 {item['query']} ({item.get('time', '')})
                    </button>
                </a>
                """,
                unsafe_allow_html=True,
            )

    if len(all_history) > limit:
        if not st.session_state["show_all_history"]:
            if st.button(f"➕ Mehr anzeigen ({len(all_history) - limit} weitere)"):
                st.session_state["show_all_history"] = True
                st.rerun()
        else:
            if st.button("➖ Weniger anzeigen (nur letzte 20)"):
                st.session_state["show_all_history"] = False
                st.rerun()
else:
    st.caption("Noch keine Artikel gescannt.")
