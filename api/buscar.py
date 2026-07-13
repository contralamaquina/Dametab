"""
Endpoint: /api/buscar
Recibe título + artista, busca "acordes/tablatura" con Serper.dev
(API gratuita de resultados de Google, sin tarjeta), y devuelve varios
resultados puntuados (0 a 5) con una heurística de confiabilidad por sitio.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import re
import urllib.request


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
# noticias/reviews, tiendas, streaming, y AHORA TAMBIÉN los sitios de letras
# más comunes (antes solo estaba genius.com, y por eso se colaban letras
# en el fallback de búsqueda amplia).
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
    "amazon.com",
    "mercadolibre.com",
    "ebay.com",
    # --- sitios de LETRAS (agregados) ---
    "genius.com",
    "letras.com",
    "letras.mus.br",
    "musica.com",
    "azlyrics.com",
    "musixmatch.com",
    "lyrics.com",
    "quedeletras.com",
    "coveralia.com",
    "vagalume.com.br",
    "megaletras.com",
    "letra.com.br",
]

PALABRAS_CLAVE_BONUS = ["acordes", "tablatura", "tab", "chords"]

# Palabras que casi siempre indican que el resultado NO es una tab en sí,
# sino una noticia, reseña, producto o LETRA que menciona la canción de paso.
PALABRAS_CLAVE_DESCARTAR_TITULO = [
    "explains", "interview", "entrevista", "review", "reseña",
    "playlist", "news", "noticia", "compra", "buy", "price", "precio",
    "documental", "biography", "biografía",
    # --- agregado: descartar explícitamente resultados de LETRAS ---
    "letra de", "letras de", "lyrics", "letra y traducción",
    "traducción de", "significado de",
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

        titulo = body.get("titulo")
        artista = body.get("artista")
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

        if body.get("debug"):
            diagnostico = self._diagnosticar(resultados, titulo)
            self._responder(200, diagnostico)
            return

        opciones = self._puntuar_y_ordenar(resultados, titulo)
        if not opciones:
            self._responder(200, {"encontrado": False})
            return

        self._responder(200, {
            "encontrado": True,
            "opciones": opciones,
        })

    def _diagnosticar(self, resultados, titulo_cancion):
        """
        Igual que _puntuar_y_ordenar pero sin descartar nada: anota el
        motivo de descarte de cada resultado para poder ver qué está
        filtrando de más (o si Serper directamente no trajo nada útil).
        """
        detalle = []
        for r in resultados:
            url_lower = r["url"].lower()
            titulo_lower = r["titulo"].lower()
            motivos = []

            sitio_bloqueado = next((s for s in SITIOS_DESCARTAR if s in url_lower), None)
            if sitio_bloqueado:
                motivos.append(f"sitio bloqueado: {sitio_bloqueado}")

            palabra_mala = next((p for p in PALABRAS_CLAVE_DESCARTAR_TITULO if p in titulo_lower), None)
            if palabra_mala:
                motivos.append(f"palabra clave descartada en título: '{palabra_mala}'")

            if not self._coincide_con_la_cancion(titulo_cancion, r):
                palabras = self._palabras_significativas(titulo_cancion)
                motivos.append(f"no coincide con el título (buscaba: {palabras})")

            detalle.append({
                "titulo": r["titulo"],
                "url": r["url"],
                "pasaria_el_filtro": len(motivos) == 0,
                "motivos_descarte": motivos,
            })

        return {
            "total_resultados_serper": len(resultados),
            "detalle": detalle,
        }

    def _buscar_en_serper(self, consulta, api_key):
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

    def _normalizar(self, texto):
        """Minúsculas, sin acentos ni signos, solo para comparar palabras."""
        texto = texto.lower()
        reemplazos = {
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
        }
        for original, plano in reemplazos.items():
            texto = texto.replace(original, plano)
        return re.sub(r"[^a-z0-9\s]", " ", texto)

    def _palabras_significativas(self, texto):
        """Palabras del título de la canción, ignorando artículos/conectores cortos."""
        IGNORAR = {"el", "la", "los", "las", "de", "del", "y", "a", "en",
                   "un", "una", "the", "of", "and", "in", "on", "to"}
        return [
            p for p in self._normalizar(texto).split()
            if p not in IGNORAR and len(p) > 2
        ]

    def _coincide_con_la_cancion(self, titulo_cancion, r):
        """
        Verifica que el resultado sea DE ESA canción puntual, y no una
        página general de la banda (ej: tabs.ultimate-guitar.com/artist/banda
        listando todas sus canciones, en vez de la tab de una en particular).
        """
        palabras = self._palabras_significativas(titulo_cancion)
        if not palabras:
            return True  # título muy corto/raro, no filtramos por esto

        texto_resultado = self._normalizar(r["titulo"] + " " + r["url"])

        coincidencias = sum(1 for p in palabras if p in texto_resultado)
        # Exigimos que aparezca al menos la mitad de las palabras
        # significativas del título (o al menos 1 si el título es de una
        # sola palabra significativa).
        minimo = max(1, len(palabras) // 2)
        return coincidencias >= minimo

    def _puntuar_y_ordenar(self, resultados, titulo_cancion):
        puntuados = []

        for r in resultados:
            url_lower = r["url"].lower()
            titulo_lower = r["titulo"].lower()

            if any(sitio in url_lower for sitio in SITIOS_DESCARTAR):
                continue

            if any(palabra in titulo_lower for palabra in PALABRAS_CLAVE_DESCARTAR_TITULO):
                continue

            # Descarta páginas genéricas de la banda que no mencionan
            # la canción puntual (ej: tab index del artista completo).
            if not self._coincide_con_la_cancion(titulo_cancion, r):
                continue

            puntaje_crudo = 0

            for sitio, valor in SITIOS_PRIORIDAD.items():
                if sitio in url_lower:
                    puntaje_crudo += valor
                    break

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
        PUNTAJE_MAXIMO = 12
        estrellas = round((puntaje_crudo / PUNTAJE_MAXIMO) * 5)
        return max(0, min(5, estrellas))

    def _responder(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
