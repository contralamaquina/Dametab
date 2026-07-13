"""
Endpoint: /api/buscar
Recibe título + artista, busca "acordes/tablatura" con Serper.dev
(API gratuita de resultados de Google, sin tarjeta), y devuelve varios
resultados puntuados (0 a 5) con una heurística de confiabilidad por sitio.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
from urllib.parse import urlparse


SITIOS_PRIORIDAD = {
    "acordes.lacuerda.net": 10,
    "lacuerda.net": 9,
    "cifraclub.com": 7,
    "cifraclub.com.br": 7,
    "ultimate-guitar.com": 6,
    "chordu.com": 4,
    "songsterr.com": 4,
}

# Además de los obvios (redes sociales, video), descartamos explícitamente
# noticias/reviews, tiendas, streaming y otros falsos positivos comunes.
SITIOS_DESCARTAR = [
    "youtube.com",
    "youtu.be",
    "pinterest.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "chords.lacuerda.net",
    "spotify.com",
    "apple.com",
    "music.amazon",
    "deezer.com",
    "soundcloud.com",
    "wikipedia.org",
    "genius.com",  # tiene letras, no tablaturas de guitarra
    "amazon.com",
    "mercadolibre.com",
    "ebay.com",
]

PALABRAS_CLAVE_BONUS = ["acordes", "tablatura", "tab", "chords"]

# Palabras que casi siempre indican que el resultado NO es una tab en sí,
# sino una noticia, reseña o producto que menciona la canción de paso.
PALABRAS_CLAVE_DESCARTAR_TITULO = [
    "explains", "interview", "entrevista", "review", "reseña",
    "playlist", "news", "noticia", "compra", "buy", "price", "precio",
    "documental", "biography", "biografía",
]


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b"{}"

        try:
            body = json.loads(crudo)
        except json.JSONDecodeError:
            self._responder(400, {"error": "Body inválido"})
            return

        titulo = (body.get("titulo") or "").strip()
        artista = (body.get("artista") or "").strip()
        if not titulo or not artista:
            self._responder(400, {"error": "Falta título o artista"})
            return

        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            self._responder(500, {"error": "Falta configurar SERPER_API_KEY"})
            return

        # 1er intento: restringir la búsqueda SOLO a los sitios de confianza,
        # usando el operador site: de Google/Serper. Esto evita por completo
        # que aparezcan noticias, playlists, tiendas, etc.
        dominios_confianza = " OR ".join(f"site:{d}" for d in SITIOS_PRIORIDAD)
        consulta_restringida = f'"{titulo}" "{artista}" ({dominios_confianza})'

        try:
            resultados = self._buscar_en_serper(consulta_restringida, api_key)
        except Exception as e:
            self._responder(500, {"error": f"Error llamando a Serper: {str(e)}"})
            return

        # 2do intento (fallback): si la búsqueda restringida no encontró nada,
        # ampliamos a toda la web pero exigimos "acordes"/"tablatura"/"chords"
        # explícitamente en la consulta para reducir ruido.
        if not resultados:
            consulta_amplia = f'"{titulo}" "{artista}" (acordes OR tablatura OR chords OR tabs) guitarra'
            try:
                resultados = self._buscar_en_serper(consulta_amplia, api_key)
            except Exception as e:
                self._responder(500, {"error": f"Error llamando a Serper: {str(e)}"})
                return

        if not resultados:
            self._responder(200, {"encontrado": False})
            return

        opciones = self._puntuar_y_ordenar(resultados)
        if not opciones:
            self._responder(200, {"encontrado": False})
            return

        self._responder(200, {
            "encontrado": True,
            "opciones": opciones,
        })

    def _buscar_en_serper(self, consulta, api_key):
        """Realiza una búsqueda en Serper.dev y retorna los resultados."""
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": consulta, "num": 8}).encode("utf-8")

        peticion = urllib.request.Request(url, data=payload, method="POST")
        peticion.add_header("X-API-KEY", api_key)
        peticion.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            data = json.loads(respuesta.read().decode("utf-8"))

        items = data.get("organic", [])
        return [
            {
                "titulo": item.get("title", ""),
                "url": item.get("link", ""),
                "descripcion": item.get("snippet", ""),
            }
            for item in items
        ]

    def _es_dominio_descartar(self, url):
        """Verifica si el dominio de la URL debe ser descartado."""
        try:
            domain = urlparse(url).netloc.lower()
            return any(domain.endswith(sitio) for sitio in SITIOS_DESCARTAR)
        except Exception:
            return False

    def _puntuar_y_ordenar(self, resultados):
        """Filtra, puntúa y ordena resultados por confiabilidad."""
        puntuados = []

        for r in resultados:
            url_lower = r["url"].lower()
            titulo_lower = r["titulo"].lower()

            # Descartar sitios en la lista negra
            if self._es_dominio_descartar(url_lower):
                continue

            # Descartar resultados con palabras clave que indican no son tabs
            if any(palabra in titulo_lower for palabra in PALABRAS_CLAVE_DESCARTAR_TITULO):
                continue

            puntaje_crudo = 0

            # Sumar puntos por sitio de prioridad
            for sitio, valor in SITIOS_PRIORIDAD.items():
                if sitio in url_lower:
                    puntaje_crudo += valor
                    break

            # Sumar puntos bonus por palabras clave en el título
            for palabra in PALABRAS_CLAVE_BONUS:
                if palabra in titulo_lower:
                    puntaje_crudo += 2

            estrellas = self._a_estrellas(puntaje_crudo)

            puntuados.append({
                "titulo": r["titulo"],
                "url": r["url"],
                "descripcion": r["descripcion"],
                "estrellas": estrellas,
            })

        puntuados.sort(key=lambda x: x["estrellas"], reverse=True)
        return puntuados

    def _a_estrellas(self, puntaje_crudo):
        """Convierte un puntaje bruto a una calificación de 0-5 estrellas."""
        PUNTAJE_MAXIMO = 12
        estrellas = round((puntaje_crudo / PUNTAJE_MAXIMO) * 5)
        return max(0, min(5, estrellas))

    def _responder(self, status_code, data):
        """Envía una respuesta JSON con el código de estado especificado."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
