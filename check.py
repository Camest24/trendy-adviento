"""Vigila maquillajetrendyshop.com y avisa cuando aparece el calendario de adviento.

Uso: python check.py   (es lo que corre GitHub Actions cada 5 minutos)
"""
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = "https://www.maquillajetrendyshop.com"
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "status.json")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

# La tienda ya tiene una colección "Calendario Adviento" (id 161). Todo lo que
# entre ahí cuenta como el calendario, se llame como se llame.
COLECCION_ADVIENTO = "161"
# Productos internos de la tienda que no son el real (p.ej. "Unidad De Prueba Ecommerce")
IGNORAR_NOMBRES = ["prueba", "test"]

# Si alguna aparece en el nombre, link o colección del producto -> "¡YA ESTÁ!"
FUERTES = [
    "adviento", "advent", "calendario", "calendar", "cuenta regresiva",
    "countdown", "24 dias", "24 sorpresas", "25 dias", "12 dias", "dias de magia",
]
# Pistas navideñas: se muestran como "posibles" y se avisan con menos prioridad
DEBILES = [
    "navidad", "navideno", "navidena", "christmas", "xmas", "holiday",
    "edicion limitada", "noche buena", "nochebuena", "papa noel", "santa",
]
# Búsquedas de texto que se le piden a la tienda
BUSQUEDAS = ["adviento", "calendario", "advent", "navidad", "navideño", "cuenta regresiva", "sorpresas"]
# Links del sitio que contienen estas palabras pero no son el producto
IGNORAR_LINKS = ["servicio-al-cliente", "terminos", "politica"]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def contiene(texto, palabras):
    t = f" {normalizar(texto)} "
    return [p for p in palabras if f" {p} " in t]


def pedir(url, como_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (vigilante-adviento)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode("utf-8", "ignore")
    return json.loads(data) if como_json else data


def productos_catalogo():
    """Colección de adviento + productos más nuevos + búsquedas por palabra clave."""
    urls = [f"{BASE}/api/catalog_system/pub/products/search?fq=productClusterIds:{COLECCION_ADVIENTO}&_from=0&_to=49"]
    urls += [f"{BASE}/api/catalog_system/pub/products/search?O=OrderByReleaseDateDESC&_from={i}&_to={i + 49}"
             for i in (0, 50)]
    urls += [f"{BASE}/api/catalog_system/pub/products/search?ft={urllib.parse.quote(q)}&_from=0&_to=49"
             for q in BUSQUEDAS]
    vistos, fallos = {}, 0
    for url in urls:
        try:
            for p in pedir(url):
                vistos[p["productId"]] = p
        except Exception as e:
            fallos += 1
            print(f"aviso: falló {url}: {e}")
    if fallos == len(urls):
        # Sin respuesta de la tienda: mejor fallar (GitHub manda correo) que
        # guardar un estado vacío que borraría lo encontrado.
        sys.exit("error: la tienda no respondió a ninguna consulta")
    return list(vistos.values())


def describir(p):
    item = p.get("items") or [{}]
    oferta = ((item[0].get("sellers") or [{}])[0]).get("commertialOffer", {})
    imagen = ((item[0].get("images") or [{}])[0]).get("imageUrl", "")
    return {
        "id": f"p{p['productId']}",
        "nombre": p.get("productName", ""),
        "link": p.get("link") or f"{BASE}/{p.get('linkText', '')}/p",
        "imagen": imagen,
        "precio": oferta.get("Price"),
        "disponible": bool(oferta.get("AvailableQuantity")),
    }


def revisar_productos():
    encontrados = []
    for p in productos_catalogo():
        if contiene(p.get("productName", ""), IGNORAR_NOMBRES):
            continue
        clusters = p.get("productClusters") or {}
        specs = [v for k in p.get("allSpecifications") or [] for v in p.get(k) or []]
        texto = " ".join([
            p.get("productName", ""), p.get("linkText", ""), p.get("productTitle", ""),
            " ".join(clusters.values()), " ".join(p.get("categories") or []), " ".join(specs),
        ])
        f, d = contiene(texto, FUERTES), contiene(texto, DEBILES)
        if COLECCION_ADVIENTO in clusters:
            f = ["colección Calendario Adviento"] + f
        if f or d:
            encontrados.append({**describir(p), "nivel": "fuerte" if f else "debil", "palabras": f or d})
    return encontrados


def revisar_portada():
    """Busca links en la portada (banners, landing pages) con palabras fuertes."""
    try:
        html = pedir(BASE + "/", como_json=False)
    except Exception as e:
        print(f"aviso: falló la portada: {e}")
        return []
    encontrados = {}
    for href in re.findall(r'href=\\?"([^"\\]+)', html):
        if any(x in href.lower() for x in IGNORAR_LINKS):
            continue
        palabras = contiene(href, FUERTES)
        if palabras:
            link = urllib.parse.urljoin(BASE + "/", href)
            encontrados[link] = {"id": "url:" + link, "nombre": "Página encontrada en la portada",
                                 "link": link, "imagen": "", "precio": None, "disponible": True,
                                 "nivel": "fuerte", "palabras": palabras}
    return list(encontrados.values())


def avisar(item, titulo):
    if not NTFY_TOPIC:
        print(f"(sin NTFY_TOPIC, no se envía aviso) {item['nombre']}")
        return
    fuerte = item["nivel"] == "fuerte"
    estado = "Disponible: ¡corre!" if item["disponible"] else "Aún no se puede comprar (te aviso cuando sí)"
    precio = f" · ${item['precio']:,.0f}".replace(",", ".") if item.get("precio") else ""
    cuerpo = {
        "topic": NTFY_TOPIC,
        "title": titulo,
        "message": f"{item['nombre']}{precio}\n{estado if fuerte else ''}\nToca para abrirlo.".replace("\n\n", "\n"),
        "click": item["link"],
        "priority": 5 if fuerte else 3,
        "tags": ["tada", "lipstick"] if fuerte else ["christmas_tree"],
        "actions": [{"action": "view", "label": "Abrir en la tienda", "url": item["link"]}],
    }
    if item.get("imagen"):
        cuerpo["attach"] = item["imagen"]
    req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()
    print(f"aviso enviado: {titulo} - {item['nombre']}")


def avisos_pendientes(item, ya_avisados):
    """Qué avisar de este item: al aparecer y, si es el calendario, cuando se pueda comprar."""
    if item["nivel"] != "fuerte":
        return [] if item["id"] in ya_avisados else [([item["id"]], "Posible producto navideño en Trendy")]
    apareció, comprable = item["id"] in ya_avisados, item["id"] + ":disponible" in ya_avisados
    if not apareció and item["disponible"]:
        return [([item["id"], item["id"] + ":disponible"], "¡YA ESTÁ el calendario de Trendy!")]
    if not apareció:
        return [([item["id"]], "¡Apareció el calendario de Trendy!")]
    if item["disponible"] and not comprable:
        return [([item["id"] + ":disponible"], "¡YA se puede comprar el calendario!")]
    return []


def main():
    try:
        anterior = json.load(open(STATUS_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        anterior = {}
    ya_avisados = set(anterior.get("avisados", []))

    items = revisar_productos() + revisar_portada()
    items.sort(key=lambda i: (i["nivel"] != "fuerte", not i["disponible"], i["nombre"]))

    for item in items:
        for claves, titulo in avisos_pendientes(item, ya_avisados):
            try:
                avisar(item, titulo)
                ya_avisados.update(claves)
            except Exception as e:
                print(f"aviso: no se pudo notificar {item['nombre']}: {e}")

    ahora = datetime.now(timezone.utc)
    estado = {
        "encontrado": any(i["nivel"] == "fuerte" for i in items),
        "items": items[:30],
        "avisados": sorted(ya_avisados),
        "ntfy_topic": NTFY_TOPIC,
        "ultima_revision": ahora.isoformat(timespec="seconds"),
    }

    # Para no llenar el repo de commits: solo se reescribe si cambió algo
    # o si la última revisión guardada tiene más de 55 minutos.
    sin_cambios = {k: v for k, v in estado.items() if k != "ultima_revision"} == \
                  {k: v for k, v in anterior.items() if k != "ultima_revision"}
    try:
        viejo = (ahora - datetime.fromisoformat(anterior["ultima_revision"])).total_seconds() > 55 * 60
    except (KeyError, ValueError):
        viejo = True
    if not sin_cambios or viejo:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=1)

    fuertes_n = sum(i["nivel"] == "fuerte" for i in items)
    print(f"revisión OK: {fuertes_n} coincidencias fuertes, {len(items) - fuertes_n} posibles")


if __name__ == "__main__":
    main()
