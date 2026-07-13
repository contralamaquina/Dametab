# Buscador de Tablaturas 🎸

App web que escucha una canción con el micrófono, la identifica con AudD,
y busca la mejor tablatura/acordes disponible en Google.

## Cómo funciona

1. El usuario graba ~10 segundos de audio desde el navegador.
2. `/api/identificar` manda ese audio a AudD y devuelve título + artista.
3. `/api/buscar` busca "título artista acordes tablatura" en Google Custom
   Search, y elige el mejor resultado con una heurística (prioriza sitios
   conocidos como lacuerda.net, cifraclub, ultimate-guitar; descarta
   YouTube, Pinterest, redes sociales).
4. Se muestra un botón para abrir esa tablatura en una pestaña nueva.

## Variables de entorno necesarias en Vercel

Configuralas en Project Settings → Environment Variables:

- `AUDD_API_KEY` — de https://audd.io
- `GOOGLE_API_KEY` — tu clave de Google Cloud (Custom Search API habilitada)
- `GOOGLE_CX` — el ID de tu motor de búsqueda programable
  (https://programmablesearchengine.google.com), configurado para
  buscar en toda la web.

## Estructura

```
/api
  identificar.py   → función serverless: audio -> canción (AudD)
  buscar.py         → función serverless: canción -> mejor link de tab (Google + heurística)
/public
  index.html         → interfaz
  app.js             → graba audio y llama a las funciones
  style.css          → estilos
vercel.json
requirements.txt
```

## Desplegar

1. Subí esta carpeta a un repo de GitHub.
2. Conectá el repo en Vercel (Import Project).
3. Cargá las 3 variables de entorno de arriba.
4. Deploy. Listo.

## Notas

- El micrófono requiere HTTPS (Vercel ya sirve todo por HTTPS, así que
  no hay que hacer nada extra).
- La heurística de `buscar.py` es editable: podés ajustar el diccionario
  `SITIOS_PRIORIDAD` para agregar o priorizar otros sitios de acordes.
- AudD y Google Custom Search tienen tiers gratis limitados; si superás
  la cuota, las funciones van a devolver error hasta el próximo período.
