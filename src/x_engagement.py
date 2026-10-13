#!/usr/bin/env python3
"""
x_engagement.py — Captura métricas reales de engagement (likes, respuestas,
retweets, quotes) de las cuentas monitoreadas y las persiste en SQLite.

Por qué existe:
    nitter_monitor.py descubre noticias vía RSS de Nitter, pero el RSS NO expone
    ningún contador de engagement. Sin esos números es imposible ordenar las
    noticias por importancia real. Este módulo cubre ese hueco usando el endpoint
    público de sindicación de X (el mismo que alimenta los tweets embebidos en
    sitios web): no requiere API key ni login, y devuelve los ~20 tweets más
    recientes de cada cuenta CON sus contadores.

Efecto secundario útil: como devuelve los últimos ~20 tweets, la primera
ejecución ya rellena varios días de histórico hacia atrás.

Uso:
    python3 x_engagement.py            # refresca todas las cuentas
    python3 x_engagement.py OpenAI     # refresca solo las cuentas indicadas

Compatible con Python 3.6 (Jetson Nano / Ubuntu 18.04).
"""

import os
import re
import ssl
import json
import time
import html
import sqlite3
import logging
import subprocess
from datetime import datetime, timedelta

import requests

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

DB_PATH = os.path.expanduser("~/.openclaw/nitter-data/engagement.sqlite")

SYNDICATION_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{}"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Pausa entre cuentas. El endpoint tolera ráfagas cortas pero empieza a
# devolver 429 alrededor de la cuenta 25 si se le pide sin pausa; como esto
# corre solo dos veces al día, tardar unos minutos no cuesta nada.
SLEEP_BETWEEN_ACCOUNTS = 6.0
# Al recibir un 429 se sube la pausa para el resto de la corrida, hasta el tope.
SLEEP_BACKOFF_FACTOR = 1.6
SLEEP_MAX = 30.0
# Espera antes de reintentar una cuenta que devolvió 429.
SLEEP_TRAS_429 = [20, 45]

# Turno de rotación del orden de consulta (ver `_orden_rotado`).
ROTACION_PATH = os.path.expanduser("~/.openclaw/nitter-data/rotacion.txt")

REQUEST_TIMEOUT = 25
MAX_RETRIES = 3

# Cuentas a consultar. Se importan de nitter_monitor.py para no mantener dos
# listas divergentes; si no se puede importar, se usa la copia de respaldo.
FALLBACK_ACCOUNTS = [
    "OpenAI", "AnthropicAI", "GoogleDeepMind", "GoogleAI", "GeminiApp",
    "AIatMeta", "DeepSeekAI", "moonshot_ai", "Grok",
    "nvidia", "AMD", "Intel", "Qualcomm", "SamsungMobile",
    "Microsoft", "AppleSupport", "Google", "Meta", "Amazon", "IBM",
    "Oracle", "GoogleCloud", "salesforce",
    "Tesla", "SpaceX", "Neuralink", "Dell", "Lenovo", "HP",
    "XiaomiEspana", "Raspberry_Pi", "Alienware", "Adobe",
    "AndroidDev", "Linux", "github",
    "sama", "ylecun", "karpathy", "elonmusk", "huggingface",
]

log = logging.getLogger("x_engagement")


def get_accounts():
    """Lee la lista de cuentas desde nitter_monitor.py para mantenerlas en sync."""
    monitor = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "nitter_monitor.py")
    if not os.path.exists(monitor):
        return list(FALLBACK_ACCOUNTS)
    try:
        with open(monitor, "r", encoding="utf-8") as f:
            src = f.read()
        # Extrae el literal X_ACCOUNTS = [...] sin ejecutar el módulo (que al
        # importarse dispararía el monitor completo y mandaría Telegrams).
        m = re.search(r"^X_ACCOUNTS\s*=\s*\[(.*?)^\]", src, re.S | re.M)
        if not m:
            return list(FALLBACK_ACCOUNTS)
        names = re.findall(r'"([A-Za-z0-9_]+)"', m.group(1))
        return names if names else list(FALLBACK_ACCOUNTS)
    except Exception as e:
        log.warning("No se pudo leer X_ACCOUNTS de nitter_monitor.py: %s", e)
        return list(FALLBACK_ACCOUNTS)


# ─────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS tweets (
    id            TEXT PRIMARY KEY,
    account       TEXT NOT NULL,
    text          TEXT,
    permalink     TEXT,
    created_at    TEXT,          -- ISO 8601 UTC
    is_retweet    INTEGER DEFAULT 0,
    likes         INTEGER DEFAULT 0,
    retweets      INTEGER DEFAULT 0,
    replies       INTEGER DEFAULT 0,
    quotes        INTEGER DEFAULT 0,
    image_url     TEXT,
    source_url    TEXT,
    first_seen    TEXT,
    last_checked  TEXT
);
CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets(created_at);
CREATE INDEX IF NOT EXISTS idx_tweets_account ON tweets(account);

-- Histórico: permite calcular velocidad de crecimiento más adelante.
CREATE TABLE IF NOT EXISTS snapshots (
    id          TEXT NOT NULL,
    checked_at  TEXT NOT NULL,
    likes       INTEGER,
    retweets    INTEGER,
    replies     INTEGER,
    quotes      INTEGER,
    PRIMARY KEY (id, checked_at)
);
"""


def connect(db_path=DB_PATH):
    """Abre (creando si hace falta) la base de datos de engagement."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Migración para bases creadas antes de la columna image_url.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tweets)")]
    if "image_url" not in cols:
        conn.execute("ALTER TABLE tweets ADD COLUMN image_url TEXT")
    if "source_url" not in cols:
        conn.execute("ALTER TABLE tweets ADD COLUMN source_url TEXT")
    conn.commit()
    return conn


# ─────────────────────────────────────────────
# PARSEO
# ─────────────────────────────────────────────

def _parse_twitter_date(raw):
    """'Thu Aug 06 18:35:55 +0000 2026' -> datetime naive UTC. None si falla."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None)
    except Exception:
        # Python 3.6 maneja %z, pero algunas variantes traen la zona pegada.
        try:
            return datetime.strptime(raw[:19] + raw[-5:], "%a %b %d %H:%M:%S%Y")
        except Exception:
            return None


def _extract_tweets(page_html, account):
    """Extrae los tweets del bloque __NEXT_DATA__ de la página de sindicación."""
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        page_html, re.S
    )
    if not m:
        return []

    try:
        data = json.loads(m.group(1))
        entries = data["props"]["pageProps"]["timeline"]["entries"]
    except (ValueError, KeyError) as e:
        log.warning("@%s: estructura inesperada (%s)", account, e)
        return []

    out = []
    for entry in entries:
        try:
            t = entry["content"]["tweet"]
        except (KeyError, TypeError):
            continue

        tid = t.get("id_str")
        if not tid:
            continue

        text = html.unescape(t.get("full_text") or t.get("text") or "")
        created = _parse_twitter_date(t.get("created_at"))

        out.append({
            "id": tid,
            # La cuenta que consultamos, no la del autor original de un RT.
            "account": account,
            "text": text,
            "permalink": "https://x.com/{}/status/{}".format(account, tid),
            "created_at": created.strftime("%Y-%m-%dT%H:%M:%S") if created else None,
            "is_retweet": 1 if text.startswith("RT @") else 0,
            "likes": int(t.get("favorite_count") or 0),
            "retweets": int(t.get("retweet_count") or 0),
            "replies": int(t.get("reply_count") or 0),
            "quotes": int(t.get("quote_count") or 0),
            "image_url": _extract_media(t),
            "source_url": _extract_source_url(t),
        })
    return out


def _extract_source_url(t):
    """
    URL del documento/página que enlaza el tweet (comunicado oficial, nota de
    prensa, etc.), o None. Es la puerta a la fuente PRIMARIA detrás del anuncio;
    se descartan enlaces de vuelta a X y a las propias imágenes.
    """
    urls = ((t.get("entities") or {}).get("urls")) or []
    for u in urls:
        ex = u.get("expanded_url") or u.get("url")
        if ex and not re.search(r"(twitter\.com|x\.com|/pic\.|pbs\.twimg|t\.co/)", ex):
            return ex
    return None


def _extract_media(t):
    """
    URL de la primera imagen del tweet, o None.

    Para fotos es la imagen directa; para video/gif es su miniatura (.jpg),
    que sirve igual como ilustración del artículo. Se mira extended_entities
    primero (lista completa de adjuntos) y luego entities como respaldo.
    """
    for clave in ("extended_entities", "entities"):
        media = ((t.get(clave) or {}).get("media")) or []
        if media:
            url = media[0].get("media_url_https") or media[0].get("media_url")
            if url:
                return url
    return None


# ¿Hay curl disponible? Se resuelve una vez (ver `_get`).
CURL = None


def _hay_curl():
    global CURL
    if CURL is None:
        try:
            subprocess.check_output(["curl", "--version"],
                                    stderr=subprocess.STDOUT)
            CURL = True
        except (OSError, subprocess.CalledProcessError):
            CURL = False
            log.warning("curl no disponible: se usa requests (más 429).")
    return CURL


def _get_curl(url):
    """
    Descarga con curl. Devuelve (status_code, texto).

    Por qué curl y no requests: el endpoint de sindicación limita por huella
    TLS, no por cabeceras. Medido el 2026-10-13 pidiendo la MISMA URL en el
    mismo instante, curl devolvía 200 con el payload completo mientras requests
    devolvía 429 de 20 bytes, con cabeceras idénticas y sin cookies. Se probaron
    tres juegos de cabeceras (solo User-Agent, navegador parcial y navegador
    completo con Sec-Fetch-*) y los tres dieron 429 desde requests: lo que la
    distingue es el handshake de urllib3, no lo que se manda en él.

    Esto explica los 2 334 "HTTP 429 persistente" acumulados en el log del blog
    —unas 11 cuentas perdidas de 44 en cada corrida— y es la razón de que
    cuentas con material de sobra no llegaran nunca al pool de noticias.
    """
    cmd = ["curl", "-s", "-m", str(REQUEST_TIMEOUT),
           "-A", USER_AGENT,
           "-H", "Accept-Language: es-MX,es;q=0.9,en;q=0.8",
           "-w", "\n%{http_code}", url]
    salida = subprocess.check_output(cmd)
    if not isinstance(salida, str):
        salida = salida.decode("utf-8", "replace")
    corte = salida.rfind("\n")
    if corte < 0:
        return 0, salida
    try:
        codigo = int(salida[corte + 1:].strip())
    except ValueError:
        codigo = 0
    return codigo, salida[:corte]


def _get(url, session):
    """Descarga por curl si está, con requests como respaldo."""
    if _hay_curl():
        return _get_curl(url)
    r = session.get(
        url,
        headers={"User-Agent": USER_AGENT,
                 "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"},
        timeout=REQUEST_TIMEOUT,
    )
    return r.status_code, r.text


def fetch_account(account, session=None):
    """
    Descarga y parsea los tweets recientes de una cuenta.

    Devuelve (tweets, hubo_429). El segundo valor permite que el bucle
    principal frene el ritmo global en cuanto aparece el primer 429, en vez
    de seguir quemando cuentas contra un límite ya activo.
    """
    sess = session or requests.Session()
    url = SYNDICATION_URL.format(account)
    hubo_429 = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            codigo, cuerpo = _get(url, sess)

            class _R(object):          # mismo trato para curl y requests
                status_code = codigo
                text = cuerpo
            r = _R()

            if r.status_code == 200 and r.text:
                tweets = _extract_tweets(r.text, account)
                if tweets:
                    return tweets, hubo_429
                log.warning("@%s: respuesta 200 pero sin tweets", account)
                return [], hubo_429

            if r.status_code == 429:
                hubo_429 = True
                if attempt < MAX_RETRIES:
                    espera = SLEEP_TRAS_429[min(attempt - 1, len(SLEEP_TRAS_429) - 1)]
                    log.warning("@%s: HTTP 429, esperando %ss (intento %s/%s)",
                                account, espera, attempt, MAX_RETRIES)
                    time.sleep(espera)
                    continue
                log.warning("@%s: HTTP 429 persistente, se omite", account)
                return [], hubo_429

            log.warning("@%s: HTTP %s (intento %s/%s)",
                        account, r.status_code, attempt, MAX_RETRIES)
        except (requests.RequestException, ssl.SSLError,
                subprocess.CalledProcessError, OSError) as e:
            log.warning("@%s: error de red (intento %s/%s): %s",
                        account, attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            time.sleep(3 * attempt)

    return [], hubo_429


# ─────────────────────────────────────────────
# PERSISTENCIA
# ─────────────────────────────────────────────

def upsert_tweets(conn, tweets):
    """Inserta o actualiza tweets y registra un snapshot. Devuelve (nuevos, actualizados)."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    nuevos = actualizados = 0
    cur = conn.cursor()

    for t in tweets:
        cur.execute("SELECT id FROM tweets WHERE id = ?", (t["id"],))
        existe = cur.fetchone() is not None

        if existe:
            cur.execute(
                """UPDATE tweets SET likes=?, retweets=?, replies=?, quotes=?,
                   image_url=COALESCE(?, image_url),
                   source_url=COALESCE(?, source_url), last_checked=? WHERE id=?""",
                (t["likes"], t["retweets"], t["replies"], t["quotes"],
                 t.get("image_url"), t.get("source_url"), now, t["id"])
            )
            actualizados += 1
        else:
            cur.execute(
                """INSERT INTO tweets
                   (id, account, text, permalink, created_at, is_retweet,
                    likes, retweets, replies, quotes, image_url, source_url,
                    first_seen, last_checked)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (t["id"], t["account"], t["text"], t["permalink"], t["created_at"],
                 t["is_retweet"], t["likes"], t["retweets"], t["replies"],
                 t["quotes"], t.get("image_url"), t.get("source_url"), now, now)
            )
            nuevos += 1

        cur.execute(
            """INSERT OR REPLACE INTO snapshots
               (id, checked_at, likes, retweets, replies, quotes) VALUES (?,?,?,?,?,?)""",
            (t["id"], now, t["likes"], t["retweets"], t["replies"], t["quotes"])
        )

    conn.commit()
    return nuevos, actualizados


def _orden_rotado(accounts):
    """
    Las mismas cuentas, pero empezando por una distinta en cada corrida.

    El endpoint de sindicación limita por IP y empieza a devolver 429 hacia la
    cuenta 16 de la tanda. Con un orden FIJO eso no reparte el castigo: se lo
    lleva siempre la misma franja. Medido sobre 213 corridas del blog, las
    posiciones 16–28 (@Google, @Meta, @Amazon, @IBM, @Oracle, @GoogleCloud,
    @salesforce, @Tesla…) perdieron entre el 26 % y el 89 % de sus capturas por
    "429 persistente", mientras que las diez primeras no perdieron ninguna. Esa
    franja quedaba fuera del pool de noticias casi siempre, y de ahí que
    cuentas con material de sobra no llegaran nunca a publicarse.

    Rotando el arranque, el coste del rate limit va rotando con él y toda la
    lista pasa por los primeros puestos con regularidad.
    """
    n = len(accounts)
    if n < 2:
        return list(accounts)

    try:
        with open(ROTACION_PATH) as f:
            turno = int((f.read() or "0").strip())
    except (IOError, ValueError):
        # Primera vez: se arranca en un punto derivado del reloj para que dos
        # procesos distintos no empiecen por la misma cuenta.
        turno = int(time.time() // 1800)

    try:
        with open(ROTACION_PATH, "w") as f:
            f.write(str((turno + 1) % n))
    except IOError:
        log.warning("No se pudo guardar el turno de rotación en %s", ROTACION_PATH)

    k = turno % n
    return list(accounts[k:]) + list(accounts[:k])


def refresh(accounts=None, conn=None):
    """Refresca el engagement de todas las cuentas. Devuelve un resumen."""
    # Solo se rota la lista completa; si quien llama pide cuentas concretas
    # (uso manual desde la línea de comandos), se respeta su orden.
    if accounts:
        accounts = list(accounts)
    else:
        accounts = _orden_rotado(get_accounts())
        log.info("Orden de consulta rotado: empieza por @%s", accounts[0])
    own_conn = conn is None
    conn = conn or connect()
    session = requests.Session()

    total_nuevos = total_act = cuentas_ok = 0
    pausa = SLEEP_BETWEEN_ACCOUNTS

    log.info("Refrescando engagement de %d cuentas...", len(accounts))
    for i, account in enumerate(accounts, 1):
        tweets, hubo_429 = fetch_account(account, session)

        if hubo_429 and pausa < SLEEP_MAX:
            pausa = min(SLEEP_MAX, pausa * SLEEP_BACKOFF_FACTOR)
            log.info("  Rate limit detectado → pausa entre cuentas: %.1fs", pausa)

        if tweets:
            n, a = upsert_tweets(conn, tweets)
            total_nuevos += n
            total_act += a
            cuentas_ok += 1
            log.info("  [%d/%d] @%-16s %2d tweets (%d nuevos)",
                     i, len(accounts), account, len(tweets), n)
        else:
            log.info("  [%d/%d] @%-16s sin datos", i, len(accounts), account)

        if i < len(accounts):
            time.sleep(pausa)

    if own_conn:
        conn.close()

    resumen = {
        "cuentas_consultadas": len(accounts),
        "cuentas_ok": cuentas_ok,
        "tweets_nuevos": total_nuevos,
        "tweets_actualizados": total_act,
    }
    log.info("Engagement: %d/%d cuentas OK, %d nuevos, %d actualizados",
             cuentas_ok, len(accounts), total_nuevos, total_act)
    return resumen


def history_days(conn):
    """
    Días que llevamos RECOLECTANDO engagement (no la antigüedad de los tweets).

    Se mide sobre first_seen: es lo que indica cuánta confianza merecen los
    contadores. Un tweet de 2019 capturado hoy no aporta histórico propio.
    """
    row = conn.execute("SELECT MIN(first_seen) AS m FROM tweets").fetchone()
    if not row or not row["m"]:
        return 0
    try:
        oldest = datetime.strptime(row["m"][:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return 0
    return max(0, (datetime.now() - oldest).days)


def recent_tweets(conn, days=3, exclude_retweets=True, min_chars=60):
    """Tweets publicados en los últimos `days` días, aptos para redactar."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    sql = "SELECT * FROM tweets WHERE created_at IS NOT NULL AND created_at >= ?"
    params = [since]
    if exclude_retweets:
        sql += " AND is_retweet = 0"
    sql += " ORDER BY created_at DESC"

    rows = [dict(r) for r in conn.execute(sql, params)]
    # Descarta tweets que son solo un enlace o una imagen: no hay nada que redactar.
    return [r for r in rows if len(_strip_urls(r.get("text") or "")) >= min_chars]


def _strip_urls(text):
    return re.sub(r"https?://\S+", "", text or "").strip()


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    cuentas = sys.argv[1:] or None
    conn = connect()
    refresh(cuentas, conn)
    print("\nHistórico disponible: {} días".format(history_days(conn)))
    print("Tweets aptos (últimos 3 días): {}".format(len(recent_tweets(conn))))
    conn.close()
