# Publicación autónoma de blog científico desde una Jetson Nano

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23353297.svg)](https://doi.org/10.5281/zenodo.23353297)

Sistema que, sin intervención humana, elige noticias de tecnología publicadas en
X (antes Twitter), redacta un artículo de divulgación científica en español con
un modelo de lenguaje y lo publica en un blog. Corre con `cron` en una NVIDIA
Jetson Nano (2020, Python 3.6) y está en producción desde el 20 de agosto
de 2026.

Este repositorio acompaña un artículo académico en preparación. Es una copia
saneada del sistema en producción: no contiene credenciales, claves de API ni
datos personales.

## Arquitectura

```
cron (00/06/12/18 h)
  └─ net-wait.sh            espera a que haya red antes de lanzar el job
       └─ salondetec_blog_auto.py   orquestador
            1. x_engagement.py      captura tuits y engagement (endpoint público
                                    de sindicación, sin API key) → SQLite
            2. selección            relevancia temática + engagement real,
                                    rotación de dominios y de fuentes
            3. redacción            Gemini / Gemma (Google AI Studio) con
                                    respaldo en OpenRouter; salida JSON
            4. referencias APA 7    construidas en código, no por el modelo
            5. publisher/           login SSO + CSRF, subida de imagen y post

cron (cada 30 min)
  └─ nitter_monitor.py      alertas a Telegram y refresco de la base
```

| Archivo | Función |
|---|---|
| `src/salondetec_blog_auto.py` | Orquestador: selección, redacción, publicación |
| `src/x_engagement.py` | Captura de tuits/engagement y base SQLite |
| `src/nitter_monitor.py` | Lista de cuentas monitoreadas y alertas |
| `src/publisher/` | Cliente del panel del blog (login, CSRF, imagen) |
| `src/net-wait.sh` | Guardia de red para los jobs de cron |
| `analysis/metricas_corridas.py` | Métricas de corridas a partir del log |

## Instalación

```bash
pip3 install -r requirements.txt
cp config.example.json config.json   # rellenar URLs, usuario, clave de API
cp .env.example .env                 # token de Telegram (opcional)
set -a; . ./.env; set +a
python3 src/salondetec_blog_auto.py --help
```

Ejemplo de `crontab`:

```
0 0,6,12,18 * * * flock -n /tmp/blog.lock /ruta/src/net-wait.sh 600 python3 /ruta/src/salondetec_blog_auto.py
*/30 * * * *      flock -n /tmp/mon.lock  /ruta/src/net-wait.sh 120 python3 /ruta/src/nitter_monitor.py
```

`config.json`, `.env`, los logs y la base SQLite están en `.gitignore`.

## Reproducir las métricas

```bash
python3 analysis/metricas_corridas.py ruta/a/blog_cron.log
```

## Notas técnicas relevantes

- El endpoint de sindicación limita por huella TLS: `requests` recibe HTTP 429
  donde `curl` recibe 200 en el mismo instante. Por eso la captura usa `curl`,
  con `requests` como respaldo.
- Con `gemini-2.5-flash` hay que desactivar el razonamiento
  (`thinkingBudget=0`); si no, consume el presupuesto de salida y trunca el JSON.
- Los modelos Gemma por la API directa ignoran el modo JSON; quedan solo como
  respaldo, con un parser tolerante.

## Licencia

MIT. Ver [LICENSE](LICENSE).

## Cómo citar

Galicia, S. (2026). *jetson-blog-autonomo: sistema autónomo de publicación de blog científico en una Jetson Nano* (Versión 1.0.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.23353297
