# Vigilante del calendario de adviento Trendy

Revisa sola https://www.maquillajetrendyshop.com cada ~10 minutos (GitHub Actions, gratis) y:

- manda una **notificación al celular** (app ntfy) con el link directo al producto;
- actualiza una **página web** (GitHub Pages) que dice "¡YA ESTÁ!" o "Todavía no".

## Cómo detecta el calendario

1. **Colección "Calendario Adviento" (id 161)** que la tienda ya creó: cualquier producto real que entre ahí cuenta.
2. Palabras clave en nombre, link, colecciones y especificaciones: adviento, calendario, advent, cuenta regresiva, 24 días…
3. Links nuevos en la portada (banners) con esas palabras.
4. Pistas navideñas (navidad, edición limitada…) salen como "posibles", con aviso de menor prioridad.

Se ignoran productos internos de prueba ("Unidad De Prueba Ecommerce").

## Archivos

- `check.py` — el vigilante (Python, sin dependencias). `python check.py --probar "pizza planet"` simula un hallazgo.
- `.github/workflows/vigilar.yml` — lo corre cada 10 min y guarda `status.json`.
- `index.html` — la página para el celular (se puede "Agregar a pantalla de inicio").

## Configuración

- Variable del repo `NTFY_TOPIC` = `trendy-adviento-8adf0d0a` (Settings → Secrets and variables → Actions → Variables).
- GitHub Pages: Settings → Pages → Deploy from branch → `main` / root.
- Para apagarlo después de noviembre: Actions → "Vigilar calendario Trendy" → Disable workflow.
