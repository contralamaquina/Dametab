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


SITIOS_PRIORIDAD = {
    "lacuerda.net": 10,
    "cifraclub.com": 7,
    "cifraclub.com.br": 7,
    "ultimate-guitar.com": 6,
    "chordu.com": 4,
    "songsterr.com": 4,
}

SITIOS_DESCARTAR = [
    "youtube.com",
    "youtu.be",
    "pinterest.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
]

PALABRAS_CLAVE_BONUS = ["acordes", "tablatura", "tab", "chords"]


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

        consulta = f'"{titulo}" "{artista}" acordes tablatura'

        try:
            resultados = self._buscar_en_serper(consulta, api_key)
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

    def _puntuar_y_ordenar(self, resultados):
        puntuados = []

        for r in resultados:
            url_lower = r["url"].lower()
            titulo_lower = r["titulo"].lower()

            if any(sitio in url_lower for sitio in SITIOS_DESCARTAR):
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
