#!/usr/bin/env python3
"""
nitter_monitor.py — Monitor de X.com via Nitter RSS con alertas a Telegram
Jetson Nano / Ubuntu 18 — Sin API key, sin tokens de LLM, 0 costo
Autor: generado para OpenClaw

INSTALACIÓN:
    pip install requests feedparser

CONFIGURACIÓN:
    Edita las variables en la sección CONFIG más abajo.

USO:
    python3 nitter_monitor.py

CRON (ejecución cada 30 minutos sin gastar tokens):
    */30 * * * * /usr/bin/python3 /home/tu_usuario/scripts/nitter_monitor.py >> /home/tu_usuario/scripts/nitter_monitor.log 2>&1
"""

import os
import sys
import json
import time
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional

# Fuente de datos: sindicación de X (misma que usa el blog). Sustituye al RSS
# de Nitter, que dejó de servir contenido (432 de 435 fetches fallaban).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_engagement

# ─────────────────────────────────────────────
# CONFIG — Edita estos valores
# ─────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # Token de tu bot de Telegram
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")    # Tu chat ID (mándale /start a @userinfobot)

# Servidores Nitter (se usan en orden, si uno falla pasa al siguiente)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]

# Cuentas de X a monitorear (sin @)
X_ACCOUNTS = [
    # ── IA y Software ──
    "OpenAI",
    "AnthropicAI",
    "GoogleDeepMind",
    "GoogleAI",
    "GeminiApp",
    "AIatMeta",       # Meta AI (verificado, antes era @MetaAI)
    "deepseek_ai",    # DeepSeek (handle real; @DeepSeekAI no tiene timeline)
    "Kimi_Moonshot",  # Kimi / Moonshot AI (handle real; @moonshot_ai no tiene timeline)
    "Grok",           # xAI Grok (verificado)
    # ── Hardware y Chips ──
    "nvidia",
    "AMD",
    "Intel",
    "Qualcomm",
    "SamsungMobile",  # Samsung (verificado)
    # ── Big Tech ──
    "Microsoft",
    "AppleSupport",  # Apple (verificado)
    "Google",
    "Meta",
    "Amazon",
    "IBM",
    # ── Cloud y Empresarial ──
    "Oracle",
    "GoogleCloud",
    "salesforce",
    # ── Electrónica y Dispositivos ──
    "Tesla",
    "SpaceX",
    "Neuralink",
    "Dell",
    "Lenovo",
    "HP",
    "XiaomiEspana",  # Xiaomi (verificado)
    "Raspberry_Pi",
    "Alienware",
    "Adobe",
    # ── Plataformas y OS ──
    "AndroidDev",    # Android (verificado)
    "Linux",
    "github",
    # ── Influencers clave (IA) ──
    "sama",           # Sam Altman
    "ylecun",         # Yann LeCun
    "karpathy",       # Andrej Karpathy
    "elonmusk",
    "huggingface",
    # ── Criptomonedas y finanzas (fuentes serias) ──
    "glassnode",      # Analítica on-chain, 100% cripto (fuente oficial)
    "CoinDesk",       # Medio de referencia (fuente oficial)
    "SECGov",         # Regulador EEUU — solo alerta si el tweet es de cripto
    # ── Solo blog (ver BLOG_ONLY_ACCOUNTS): amplían los dominios del blog ──
    "NASA",
    "esa",
    "NASAJPL",
    "RocketLab",
    "BostonDynamics",
    "Waymo",
    "NIH",
    "ENERGY",
    "IEA",
    "CISAgov",
    "Cloudflare",
    "Arm",
    "MicronTech",
    "perplexity_ai",
    "cohere",
]

# Cuentas que solo alimentan la base de engagement del blog, sin alertas a
# Telegram. Se sumaron el 2026-10-13 tras el análisis de contenido: el 59 % del
# material disponible era de IA y dominios como espacio, salud, energía o
# ciberseguridad casi no tenían fuentes. Publican mucho (NASA, IEA y CISA
# rondan 20 tuits por semana), así que alertar todo inundaría el chat.
BLOG_ONLY_ACCOUNTS = {
    "NASA", "esa", "NASAJPL", "RocketLab", "BostonDynamics", "Waymo", "NIH",
    "ENERGY", "IEA", "CISAgov", "Cloudflare", "Arm", "MicronTech",
    "perplexity_ai", "cohere",
}

# Cuentas de influencers/personas (solo alertan si hay keyword match)
INFLUENCER_ACCOUNTS = {
    "sama",           # Sam Altman
    "ylecun",         # Yann LeCun
    "karpathy",       # Andrej Karpathy
    "elonmusk",
}

# Cuentas que solo alertan cuando el tweet trata de criptomonedas. Útil para
# fuentes de máxima autoridad que cubren un espectro más amplio (p.ej. la SEC
# regula todo el mercado de valores, no solo cripto): así evitamos el ruido no
# relacionado y conservamos solo lo relevante al tema.
CRYPTO_FILTER_ACCOUNTS = {
    "SECGov",
}

# Keywords de criptomonedas para ese filtro (case-insensitive).
CRYPTO_KEYWORDS = [
    "crypto", "cripto", "bitcoin", "btc", "ethereum", "eth", "blockchain",
    "digital asset", "activo digital", "stablecoin", "token", "defi",
    "web3", "coinbase", "binance", "ripple", "xrp", "solana", "etf",
    "custody", "custodia", "exchange",
]

# Keywords que disparan la alerta (case-insensitive) — solo para influencers
KEYWORDS = [
    "OpenClaw",
    "AI Agent",
    "AI Agents",
    "Arduino",
    "Robótica",
    "Robotica",
    "Robotic",
    "Inteligencia Artificial",
    "Artificial Intelligence",
    "OpenAI",
    "Anthropic",
    "Google",
    "Gemini",
    "Minimax",
    "Claude",
    "Grok",
    "NVidia",
    "Microsoft",
    "Copilot",
    "Apple",
    "LLM",
    "GPT",
    "Agent",
    "Jetson",
    "open source",
]

# Archivo donde se guardan los posts ya vistos (evita duplicados)
SEEN_FILE = os.path.expanduser("~/.openclaw/nitter_seen.json")

# Directorio donde se guardan los posts completos para análisis diario
NITTER_DATA_DIR = os.path.expanduser("~/.openclaw/nitter-data")

# Cuántos posts revisar por cuenta (para no saturar)
MAX_ITEMS_PER_FEED = 10

# Solo se alerta de tweets publicados dentro de esta ventana. Es la salvaguarda
# contra spam: sindicación devuelve el historial reciente de cada cuenta (hasta
# ~100 tweets), así que sin este filtro la primera corrida tras migrar mandaría
# cientos de alertas viejas. Con el cron cada 30 min, 3 h da margen de sobra
# para no perder nada aunque una corrida falle.
MAX_EDAD_HORAS = 3

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# FUNCIONES
# ─────────────────────────────────────────────

def load_seen() -> set:
    """Carga los IDs de posts ya procesados."""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen: set):
    """Guarda los IDs procesados, mantiene solo los últimos 2000."""
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    seen_list = list(seen)[-2000:]  # evita que el archivo crezca infinito
    with open(SEEN_FILE, "w") as f:
        json.dump(seen_list, f)


def save_post_data(account: str, entry, is_influencer: bool, keyword: str = None):
    """
    Guarda datos del post en JSON diario para análisis posterior.

    Conserva el mismo esquema (con 'link' conteniendo /status/<id>) del que
    depende salondetec_blog_auto.py para saber qué noticias ya se enviaron por
    Telegram. Ahora además incluye las métricas de engagement.
    """
    os.makedirs(NITTER_DATA_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    data_file = os.path.join(NITTER_DATA_DIR, f"{today}.json")

    posts = []
    if os.path.exists(data_file):
        try:
            with open(data_file, "r") as f:
                posts = json.load(f)
        except Exception:
            posts = []

    post = {
        "account": account,
        "title": entry.get("text", "Sin título")[:300],
        "link": entry.get("permalink", ""),
        "summary": entry.get("text", "")[:500],
        "published": entry.get("created_at", ""),
        "likes": entry.get("likes", 0),
        "replies": entry.get("replies", 0),
        "retweets": entry.get("retweets", 0),
        "is_influencer": is_influencer,
        "keyword_match": keyword,
        "timestamp": datetime.now().isoformat(),
    }
    posts.append(post)

    with open(data_file, "w") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def post_id(entry) -> str:
    """
    ID único del post. Usa el id numérico del tweet (estable entre corridas);
    si faltara, cae al hash del permalink como respaldo.
    """
    tid = entry.get("id")
    if tid:
        return str(tid)
    return hashlib.md5((entry.get("permalink", "") or "").encode()).hexdigest()


def es_reciente(entry) -> bool:
    """True si el tweet se publicó dentro de la ventana MAX_EDAD_HORAS."""
    fecha = entry.get("created_at")
    if not fecha:
        return False
    try:
        dt = datetime.strptime(fecha[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return (datetime.now() - dt) <= timedelta(hours=MAX_EDAD_HORAS)


def contains_keyword(text: str) -> Optional[str]:
    """Retorna la primera keyword encontrada en el texto, o None."""
    text_lower = text.lower()
    for kw in KEYWORDS:
        if kw.lower() in text_lower:
            return kw
    return None


def contains_crypto(text: str) -> Optional[str]:
    """Retorna la primera keyword de cripto encontrada en el texto, o None."""
    text_lower = " " + (text or "").lower() + " "
    for kw in CRYPTO_KEYWORDS:
        # Bordes para términos cortos y ambiguos (btc, eth, etf, defi...),
        # coincidencia simple para el resto.
        if len(kw) <= 4:
            if (" " + kw + " ") in text_lower or (" " + kw + ",") in text_lower:
                return kw
        elif kw in text_lower:
            return kw
    return None


def fetch_feed(account: str, session=None) -> list:
    """
    Obtiene los tweets recientes de una cuenta vía sindicación de X.

    Devuelve una lista de dicts (el formato de x_engagement): id, text,
    permalink, created_at, likes, replies, retweets, quotes, is_retweet.
    """
    tweets = x_engagement.fetch_account(account, session)[0]
    if tweets:
        log.info(f"✅ {account}: {len(tweets)} posts")
    else:
        log.warning(f"❌ Sin datos para @{account}")
    return tweets[:MAX_ITEMS_PER_FEED]


def send_telegram(message: str):
    """Envía un mensaje a Telegram."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log.info("📨 Alerta enviada a Telegram")
        else:
            log.error(f"Telegram error: {r.status_code} — {r.text}")
    except Exception as e:
        log.error(f"Error enviando a Telegram: {e}")


def _metricas(entry) -> str:
    """Línea de engagement para las alertas."""
    return (f"❤️ {entry.get('likes', 0)}  "
            f"💬 {entry.get('replies', 0)}  "
            f"🔁 {entry.get('retweets', 0)}")


def format_alert(account: str, entry, keyword: str) -> str:
    """Formatea el mensaje de alerta para Telegram (influencers, con keyword)."""
    import html as _html
    title = _html.escape(entry.get("text", "Sin título")[:300])
    return (
        f"🔔 <b>Alerta X.com</b>\n"
        f"👤 <b>@{account}</b>\n"
        f"🏷️ Keyword: <code>{keyword}</code>\n"
        f"📝 {title}\n"
        f"📊 {_metricas(entry)}\n"
        f"🔗 {entry.get('permalink', '')}"
    )


def format_alert_official(account: str, entry) -> str:
    """Formatea alerta de fuente oficial (sin filtro de keyword)."""
    import html as _html
    title = _html.escape(entry.get("text", "Sin título")[:300])
    return (
        f"📡 <b>Fuente Oficial</b>\n"
        f"👤 <b>@{account}</b>\n"
        f"📝 {title}\n"
        f"📊 {_metricas(entry)}\n"
        f"🔗 {entry.get('permalink', '')}"
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    log.info("🚀 Iniciando monitor X (sindicación)")
    log.info(f"📋 Cuentas: {len(X_ACCOUNTS)} | Keywords: {len(KEYWORDS)}")
    log.info(f"🏷️  Influencers (con filtro): {len(INFLUENCER_ACCOUNTS)}")
    log.info(f"⏱️  Ventana de frescura: {MAX_EDAD_HORAS} h")

    seen = load_seen()
    new_alerts = 0
    session = requests.Session()

    # De paso, el monitor mantiene al día la base de engagement que usan el
    # blog y los borradores de LinkedIn. Si algo falla aquí, no se aborta el
    # monitoreo: las alertas son la función principal.
    try:
        eng_conn = x_engagement.connect()
    except Exception as e:
        log.warning(f"No se pudo abrir la base de engagement: {e}")
        eng_conn = None

    for account in X_ACCOUNTS:
        entries = fetch_feed(account, session)
        is_influencer = account in INFLUENCER_ACCOUNTS

        if eng_conn is not None and entries:
            try:
                x_engagement.upsert_tweets(eng_conn, entries)
            except Exception as e:
                log.warning(f"upsert @{account}: {e}")

        if account in BLOG_ONLY_ACCOUNTS:
            time.sleep(x_engagement.SLEEP_BETWEEN_ACCOUNTS)
            continue  # ya quedó en la base; no se alerta

        for entry in entries:
            # Salvaguarda anti-spam: ignorar lo que no sea reciente.
            if not es_reciente(entry):
                continue

            pid = post_id(entry)
            if pid in seen:
                continue  # ya procesado
            seen.add(pid)

            # Los retweets no son noticia de la propia cuenta.
            if entry.get("is_retweet"):
                continue

            if account in CRYPTO_FILTER_ACCOUNTS:
                # Fuente de autoridad amplia: solo alertar si habla de cripto.
                keyword = contains_crypto(entry.get("text", ""))
                if keyword:
                    log.info(f"🪙 Cripto: @{account} → '{keyword}'")
                    send_telegram(format_alert(account, entry, keyword))
                    save_post_data(account, entry, False, keyword)
                    new_alerts += 1
                    time.sleep(2)
            elif is_influencer:
                # Influencers: solo alertar si hay keyword match
                keyword = contains_keyword(entry.get("text", ""))
                if keyword:
                    log.info(f"🎯 Match: @{account} → '{keyword}'")
                    send_telegram(format_alert(account, entry, keyword))
                    save_post_data(account, entry, True, keyword)
                    new_alerts += 1
                    time.sleep(2)
            else:
                # Fuentes oficiales: enviar todo sin filtro
                log.info(f"📡 Oficial: @{account}")
                send_telegram(format_alert_official(account, entry))
                save_post_data(account, entry, False)
                new_alerts += 1
                time.sleep(2)

        time.sleep(x_engagement.SLEEP_BETWEEN_ACCOUNTS)  # pausa entre cuentas

    save_seen(seen)
    if eng_conn is not None:
        eng_conn.close()
    log.info(f"✅ Fin. Alertas enviadas: {new_alerts}")


if __name__ == "__main__":
    main()
