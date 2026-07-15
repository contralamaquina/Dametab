"""
Endpoint: /api/identificar
Recibe audio en base64 (grabado desde el navegador) y trata de reconocer
la canción usando dos motores en cadena:

  1. AudD          (motor principal)
  2. ACRCloud       (fallback si AudD no encuentra nada)

Si ninguno de los dos reconoce la canción, se devuelve encontrada=False
para que el frontend le pregunte al usuario el artista/título a mano.
"""

from http.server import BaseHTTPRequestHandler
import base64
import hashlib
import hmac
import json
import os
import time
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

        resultado, motor_usado, errores = self._identificar_con_fallback(audio_base64)

        if resultado is None:
            # Ningún motor pudo identificarla. No es un error del servidor,
            # es un resultado válido: "no encontrada". El frontend decide
            # qué hacer (pedirle al usuario artista/título a mano).
            self._responder(200, {
                "encontrada": False,
                "errores": errores,  # útil para debug, el frontend lo ignora
            })
            return

        resultado["motor"] = motor_usado
        self._responder(200, resultado)

    def _identificar_con_fallback(self, audio_base64):
        """
        Prueba AudD primero. Si no encuentra nada (o falla), prueba ACRCloud.
        Devuelve (resultado_o_None, nombre_motor_o_None, lista_de_errores).
        """
        errores = []

        audd_key = os.environ.get("AUDD_API_KEY")
        if audd_key:
            try:
                resultado = self._identificar_con_audd(audio_base64, audd_key)
                if resultado:
                    return resultado, "audd", errores
            except Exception as e:
                errores.append(f"AudD: {str(e)}")
        else:
            errores.append("AudD: falta configurar AUDD_API_KEY")

        acr_host = os.environ.get("ACRCLOUD_HOST")
        acr_key = os.environ.get("ACRCLOUD_ACCESS_KEY")
        acr_secret = os.environ.get("ACRCLOUD_ACCESS_SECRET")
        if acr_host and acr_key and acr_secret:
            try:
                resultado = self._identificar_con_acrcloud(
                    audio_base64, acr_host, acr_key, acr_secret
                )
                if resultado:
                    return resultado, "acrcloud", errores
            except Exception as e:
                errores.append(f"ACRCloud: {str(e)}")
        else:
            errores.append("ACRCloud: faltan variables de entorno")

        return None, None, errores

    # ---------------------------------------------------------------
    # AudD
    # ---------------------------------------------------------------

    def _identificar_con_audd(self, audio_base64, api_key):
        """Llama a la API de AudD. Devuelve dict listo para responder, o None."""
        url = "https://api.audd.io/"

        datos = urllib.parse.urlencode({
            "api_token": api_key,
            "audio": audio_base64,
            "return": "apple_music,spotify",
        }).encode("utf-8")

        peticion = urllib.request.Request(url, data=datos, method="POST")
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            resultado = json.loads(respuesta.read().decode("utf-8"))

        if resultado.get("status") != "success":
            raise Exception("AudD no pudo procesar el audio")

        datos_cancion = resultado.get("result")
        if not datos_cancion:
            return None  # AudD entendió el audio pero no reconoció la canción

        return {
            "encontrada": True,
            "titulo": datos_cancion.get("title"),
            "artista": datos_cancion.get("artist"),
            "album": datos_cancion.get("album"),
            "portada": self._extraer_portada_audd(datos_cancion),
        }

    def _extraer_portada_audd(self, datos_cancion):
        spotify = datos_cancion.get("spotify")
        if spotify:
            imagenes = spotify.get("album", {}).get("images", [])
            if imagenes:
                return imagenes[0].get("url")

        apple_music = datos_cancion.get("apple_music")
        if apple_music:
            artwork = apple_music.get("artwork", {})
            url = artwork.get("url")
            if url:
                return url.replace("{w}", "300").replace("{h}", "300")

        return None

    # ---------------------------------------------------------------
    # ACRCloud
    # ---------------------------------------------------------------

    def _identificar_con_acrcloud(self, audio_base64, host, access_key, access_secret):
        """Llama a la API de reconocimiento de ACRCloud. Devuelve dict o None."""
        audio_bytes = base64.b64decode(audio_base64)

        endpoint = "/v1/identify"
        timestamp = str(int(time.time()))
        signature_version = "1"
        http_method = "POST"

        cadena_a_firmar = "\n".join([
            http_method,
            endpoint,
            access_key,
            "audio",
            signature_version,
            timestamp,
        ])

        firma = base64.b64encode(
            hmac.new(
                access_secret.encode("utf-8"),
                cadena_a_firmar.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        boundary = "----DameTabBoundary"

        campos = {
            "access_key": access_key,
            "sample_bytes": str(len(audio_bytes)),
            "timestamp": timestamp,
            "signature": firma,
            "data_type": "audio",
            "signature_version": signature_version,
        }

        cuerpo = bytearray()
        for nombre, valor in campos.items():
            cuerpo.extend(f"--{boundary}\r\n".encode("utf-8"))
            cuerpo.extend(f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'.encode("utf-8"))
            cuerpo.extend(f"{valor}\r\n".encode("utf-8"))

        cuerpo.extend(f"--{boundary}\r\n".encode("utf-8"))
        cuerpo.extend(
            'Content-Disposition: form-data; name="sample"; filename="sample.webm"\r\n'.encode("utf-8")
        )
        cuerpo.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        cuerpo.extend(audio_bytes)
        cuerpo.extend(b"\r\n")
        cuerpo.extend(f"--{boundary}--\r\n".encode("utf-8"))

        url = f"https://{host}{endpoint}"
        peticion = urllib.request.Request(url, data=bytes(cuerpo), method="POST")
        peticion.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            resultado = json.loads(respuesta.read().decode("utf-8"))

        status = resultado.get("status", {})
        codigo = status.get("code")

        if codigo == 1001:
            # 1001 = "no match found": no es un error, simplemente no la reconoció
            return None

        if codigo != 0:
            raise Exception(status.get("msg", f"código de error {codigo}"))

        metadata = resultado.get("metadata", {})
        musicas = metadata.get("music", [])
        if not musicas:
            return None

        cancion = musicas[0]
        titulo = cancion.get("title")
        artistas = cancion.get("artists", [])
        artista = artistas[0].get("name") if artistas else None

        album = cancion.get("album", {}).get("name")
        portada = self._extraer_portada_acrcloud(cancion)

        return {
            "encontrada": True,
            "titulo": titulo,
            "artista": artista,
            "album": album,
            "portada": portada,
        }

    def _extraer_portada_acrcloud(self, cancion):
        """
        ACRCloud a veces trae datos externos de Spotify/Apple Music dentro
        de 'external_metadata', igual que AudD. Si no hay, no hay portada.
        """
        externos = cancion.get("external_metadata", {})

        spotify = externos.get("spotify")
        if spotify:
            album_id = spotify.get("album", {}).get("id")
            # ACRCloud no siempre da la URL de la imagen directamente;
            # si no está disponible, simplemente no mostramos portada.
            imagenes = spotify.get("album", {}).get("images")
            if imagenes:
                return imagenes[0].get("url")

        apple_music = externos.get("apple_music")
        if apple_music:
            artwork = apple_music.get("artwork", {})
            url = artwork.get("url")
            if url:
                return url.replace("{w}", "300").replace("{h}", "300")

        return None

    # ---------------------------------------------------------------

    def _responder(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
