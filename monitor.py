#!/usr/bin/env python3
"""Rastreador ligero de ofertas RTX 5090 en canales publicos de Telegram."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = ROOT / "state.json"
REPORT_PATH = ROOT / "latest.md"
DOCS_PATH = ROOT / "docs" / "index.html"
NEW_PATH = ROOT / "new_offers.json"

MESSAGE_RE = re.compile(
    r'<div class="tgme_widget_message_wrap[^>]*>.*?'
    r'<div class="tgme_widget_message[^>]*data-post="(?P<post>[^"]+)".*?'
    r'</div>\s*</div>\s*</div>\s*</div>',
    re.IGNORECASE | re.DOTALL,
)
DATETIME_RE = re.compile(r'<time[^>]+datetime="([^"]+)"', re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
PRICE_PATTERNS = (
    re.compile(r"€\s*([0-9][0-9.,\s]{2,})"),
    re.compile(r"([0-9][0-9.,\s]{2,})\s*(?:€|EUR)\b", re.IGNORECASE),
)
PROBLEM_TERMS = (
    "defect",
    "defekt",
    "broken",
    "averiad",
    "sin devolucion",
    "sin devolución",
    "for parts",
)


def classify_offer(text: str) -> tuple[str, str, int]:
    folded = text.casefold()
    if any(term in folded for term in PROBLEM_TERMS):
        return "Tarjeta gráfica", "Averiada o para piezas", 2
    if any(term in folded for term in ("portatil", "portátil", "laptop", "notebook")):
        return "Portátil", "Sin confirmar", 0
    if any(term in folded for term in ("pc completo", "gaming pc", "ordenador", "desktop pc")):
        return "PC completo", "Sin confirmar", 0
    if any(term in folded for term in ("refurb", "reacondicion", "renewed")):
        return "Tarjeta gráfica", "Reacondicionada", 1
    if any(term in folded for term in ("used", "usada", "gebraucht", "segunda mano")):
        return "Tarjeta gráfica", "Usada", 1
    return "Tarjeta gráfica", "Nueva o sin confirmar", 0


def value_rating(price: float, penalty: int = 0) -> int:
    if price <= 2400:
        rating = 5
    elif price <= 3200:
        rating = 4
    elif price <= 4500:
        rating = 3
    elif price <= 6500:
        rating = 2
    else:
        rating = 1
    return max(1, rating - penalty)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(url: str, timeout: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/127 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    fragment = TAG_RE.sub(" ", fragment)
    return " ".join(html.unescape(fragment).split())


def normalize_price(raw: str) -> float | None:
    value = raw.replace(" ", "").strip(".,")
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        tail = value.rsplit(",", 1)[1]
        value = value.replace(",", ".") if len(tail) == 2 else value.replace(",", "")
    elif value.count(".") == 1 and len(value.rsplit(".", 1)[1]) == 3:
        value = value.replace(".", "")
    try:
        price = float(value)
    except ValueError:
        return None
    return price if 500 <= price <= 20000 else None


def extract_prices(text: str) -> list[float]:
    prices: list[float] = []
    for pattern in PRICE_PATTERNS:
        for match in pattern.finditer(text):
            price = normalize_price(match.group(1))
            if price is not None:
                prices.append(price)
    return prices


def scan_telegram(
    source: dict, page: str, max_price: float, max_post_age_hours: int
) -> list[dict]:
    findings: list[dict] = []
    for match in MESSAGE_RE.finditer(page):
        fragment = match.group(0)
        text = clean_text(fragment)
        folded = text.casefold()
        if "rtx 5090" not in folded and "rtx5090" not in folded:
            continue
        if re.search(r'to\s+["“]?out of stock', folded):
            continue
        prices = extract_prices(text)
        qualifying = [price for price in prices if price <= max_price]
        if not qualifying:
            continue
        date_match = DATETIME_RE.search(fragment)
        if not date_match:
            continue
        try:
            posted = datetime.fromisoformat(date_match.group(1).replace("Z", "+00:00"))
        except ValueError:
            continue
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_post_age_hours)
        if posted.astimezone(timezone.utc) < cutoff:
            continue
        post = match.group("post")
        category, condition, penalty = classify_offer(text)
        price = min(qualifying)
        findings.append(
            {
                "id": post,
                "source": source["name"],
                "price_eur": price,
                "category": category,
                "condition": condition,
                "rating": value_rating(price, penalty),
                "url": f"https://t.me/{post}",
                "date": date_match.group(1),
                "summary": text[:240],
            }
        )
    return findings


def scan_web(source: dict, page: str, max_price: float) -> list[dict]:
    text = clean_text(page)
    folded = text.casefold()
    if "rtx 5090" not in folded and "rtx5090" not in folded:
        return []
    unavailable = [term.casefold() for term in source.get("unavailable_terms", [])]
    if any(term in folded for term in unavailable):
        return []
    price = float(source.get("price_eur", 0))
    if not 500 <= price <= max_price:
        return []
    category, condition, penalty = classify_offer(text)
    return [
        {
            "id": source["url"],
            "source": source["name"],
            "price_eur": price,
            "category": source.get("category", category),
            "condition": source.get("condition", condition),
            "rating": value_rating(price, penalty),
            "url": source["url"],
            "date": datetime.now(timezone.utc).isoformat(),
            "summary": text[:240],
        }
    ]


def render_report(findings: list[dict], excellent_price: float, errors: list[str]) -> str:
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [
        "# Resultados del monitor RTX 5090",
        "",
        f"Última comprobación: {timestamp}",
        "",
    ]
    if findings:
        lines += ["| Valoración | Precio | Tipo | Estado | Fuente | Fecha | Enlace |", "|---|---:|---|---|---|---|---|"]
        for item in sorted(findings, key=lambda row: (-row["rating"], row["price_eur"])):
            level = "★" * item["rating"] + "☆" * (5 - item["rating"])
            date = item["date"][:10] or "Sin fecha"
            lines.append(
                f"| {level} | {item['price_eur']:.2f} € | {item['category']} | {item['condition']} | {item['source']} | "
                f"{date} | [Abrir oferta]({item['url']}) |"
            )
    else:
        lines.append("No se encontraron publicaciones dentro del límite configurado.")
    if errors:
        lines += ["", "## Fuentes que no respondieron", ""]
        lines.extend(f"- {error}" for error in errors)
    lines.append("")
    return "\n".join(lines)


def render_html(findings: list[dict], excellent_price: float, errors: list[str]) -> str:
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M %Z")
    cards = []
    for item in sorted(findings, key=lambda row: (-row["rating"], row["price_eur"])):
        level = "★" * item["rating"] + "☆" * (5 - item["rating"])
        cards.append(
            '<article class="offer">'
            f'<span class="badge">{html.escape(level)}</span>'
            f'<h2>{item["price_eur"]:.2f} €</h2>'
            f'<p><strong>{html.escape(item["category"])}</strong> · {html.escape(item["condition"])}</p>'
            f'<p>{html.escape(item["source"])}</p>'
            f'<a href="{html.escape(item["url"], quote=True)}" target="_blank" rel="noopener">Abrir oferta</a>'
            '</article>'
        )
    content = "".join(cards) or (
        '<section class="empty"><h2>No hay ofertas que cumplan el límite</h2>'
        '<p>Volveremos a comprobar las fuentes automáticamente.</p></section>'
    )
    warning = ""
    if errors:
        warning = f'<p class="warning">Fuentes temporalmente inaccesibles: {len(errors)}</p>'
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ofertas internacionales RTX 5090</title><style>
:root{{--bg:#080b12;--panel:#121826;--text:#f5f7fb;--muted:#aab4c5;--accent:#76b900}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(145deg,#080b12,#111827);color:var(--text);font:16px system-ui,sans-serif;min-height:100vh}}
main{{max-width:900px;margin:auto;padding:48px 20px}}h1{{font-size:clamp(2rem,6vw,4rem);margin:.2em 0}}header p,.empty p{{color:var(--muted)}}
.status{{display:inline-block;color:#b9f36a;border:1px solid #4b6f24;border-radius:999px;padding:7px 12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:28px}}
.offer,.empty{{background:rgba(18,24,38,.9);border:1px solid #263044;border-radius:18px;padding:24px;box-shadow:0 14px 40px #0005}}.offer h2{{font-size:2rem;margin:14px 0 6px}}
.badge{{font-size:.8rem;background:#27430b;color:#caff8e;border-radius:999px;padding:6px 9px}}a{{display:inline-block;margin-top:12px;color:#111;background:var(--accent);padding:10px 14px;border-radius:10px;text-decoration:none;font-weight:700}}
.warning{{color:#ffd479}}footer{{margin-top:36px;color:var(--muted);font-size:.9rem}}
</style></head><body><main><header><span class="status">● Monitor activo 24/7</span><h1>RTX 5090: ofertas internacionales</h1><p>Valoradas de mejor a peor · Precio máximo 10.000 € · Tarjetas, equipos y portátiles</p></header>
{warning}<section class="grid">{content}</section><footer>Última comprobación: {html.escape(timestamp)} · Mercados internacionales · Actualización cada 5 minutos.</footer></main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Busca ofertas RTX 5090 en Telegram público")
    parser.add_argument("--all", action="store_true", help="muestra también publicaciones ya vistas")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"seen": []})
    seen = set(state.get("seen", []))
    timeout = int(config.get("request_timeout_seconds", 20))
    max_price = float(config.get("max_price_eur", 2800))
    max_post_age_hours = int(config.get("max_post_age_hours", 72))
    excellent_price = float(config.get("excellent_price_eur", 2400))
    findings: list[dict] = []
    errors: list[str] = []

    for source in config.get("telegram_sources", []):
        try:
            page = fetch(source["url"], timeout)
            findings.extend(scan_telegram(source, page, max_price, max_post_age_hours))
        except Exception as exc:  # continuar con las demás fuentes
            errors.append(f"{source['name']}: {type(exc).__name__}")

    for source in config.get("web_sources", []):
        try:
            page = fetch(source["url"], timeout)
            findings.extend(scan_web(source, page, max_price))
        except Exception as exc:
            errors.append(f"{source['name']}: {type(exc).__name__}")

    unique = {item["id"]: item for item in findings}
    all_findings = list(unique.values())
    visible = all_findings if args.all else [item for item in all_findings if item["id"] not in seen]
    REPORT_PATH.write_text(render_report(visible, excellent_price, errors), encoding="utf-8")
    NEW_PATH.write_text(json.dumps(visible, indent=2, ensure_ascii=False), encoding="utf-8")
    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.write_text(render_html(all_findings, excellent_price, errors), encoding="utf-8")

    state["seen"] = sorted(seen | set(unique))
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    print(REPORT_PATH.read_text(encoding="utf-8"))
    # Una tienda puede bloquear temporalmente el rastreo; el informe sigue siendo válido
    # si el resto de fuentes se procesó. Las fuentes fallidas aparecen en el informe.
    return 0


if __name__ == "__main__":
    sys.exit(main())

