"""
Endpoint: /api/identificar
Recibe audio en base64 (grabado desde el navegador), lo manda a AudD
y devuelve el nombre de la canción + artista identificados.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b"{}"

        try:
            body = json.loads(crudo)
        except json.JSONDecodeError:
            self._responder(400, {"error": "Body inválido"})
            return

        audio_base64 = body.get("audio")
        if not audio_base64:
            self._responder(400, {"error": "Falta el audio"})
            return

        api_key = os.environ.get("AUDD_API_KEY")
        if not api_key:
            self._responder(500, {"error": "Falta configurar AUDD_API_KEY"})
            return

        try:
            resultado = self._identificar_con_audd(audio_base64, api_key)
        except Exception as e:
            self._responder(500, {"error": f"Error llamando a AudD: {str(e)}"})
            return

        if resultado.get("status") != "success":
            self._responder(500, {"error": "AudD no pudo procesar el audio"})
            return

        datos_cancion = resultado.get("result")
        if not datos_cancion:
            self._responder(200, {"encontrada": False})
            return

        self._responder(200, {
            "encontrada": True,
            "titulo": datos_cancion.get("title"),
            "artista": datos_cancion.get("artist"),
            "album": datos_cancion.get("album"),
            "portada": self._extraer_portada(datos_cancion),
        })

    def _extraer_portada(self, datos_cancion):
        """
        AudD puede devolver datos extra de Spotify o Apple Music (si se
        pidieron con el parámetro 'return'). De ahí sacamos la imagen de
        portada del álbum, si está disponible.
        """
        spotify = datos_cancion.get("spotify")
        if spotify:
            imagenes = spotify.get("album", {}).get("images", [])
            if imagenes:
                # Spotify devuelve varios tamaños; el primero suele ser el más grande.
                return imagenes[0].get("url")

        apple_music = datos_cancion.get("apple_music")
        if apple_music:
            artwork = apple_music.get("artwork", {})
            url = artwork.get("url")
            if url:
                # La URL de Apple Music trae placeholders {w}x{h} para el tamaño.
                return url.replace("{w}", "300").replace("{h}", "300")

        return None

    def _identificar_con_audd(self, audio_base64, api_key):
        """Llama a la API de AudD con el audio en base64."""
        url = "https://api.audd.io/"

        datos = urllib.parse.urlencode({
            "api_token": api_key,
            "audio": audio_base64,
            "return": "apple_music,spotify",
        }).encode("utf-8")

        peticion = urllib.request.Request(url, data=datos, method="POST")
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))

    def _responder(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
