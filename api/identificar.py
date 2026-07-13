"""
Endpoint: /api/identificar
Recibe audio en base64 (grabado desde el navegador), lo manda a AudD
y devuelve el nombre de la canción + artista identificados.
"""

import json
import os
import base64
import urllib.request
import urllib.parse


def handler(request):
    if request.get("method") != "POST":
        return _respuesta(405, {"error": "Método no permitido"})

    try:
        body = json.loads(request.get("body", "{}"))
    except json.JSONDecodeError:
        return _respuesta(400, {"error": "Body inválido"})

    audio_base64 = body.get("audio")
    if not audio_base64:
        return _respuesta(400, {"error": "Falta el audio"})

    api_key = os.environ.get("AUDD_API_KEY")
    if not api_key:
        return _respuesta(500, {"error": "Falta configurar AUDD_API_KEY"})

    try:
        resultado = _identificar_con_audd(audio_base64, api_key)
    except Exception as e:
        return _respuesta(500, {"error": f"Error llamando a AudD: {str(e)}"})

    if resultado.get("status") != "success":
        return _respuesta(500, {"error": "AudD no pudo procesar el audio"})

    datos_cancion = resultado.get("result")
    if not datos_cancion:
        return _respuesta(200, {"encontrada": False})

    return _respuesta(200, {
        "encontrada": True,
        "titulo": datos_cancion.get("title"),
        "artista": datos_cancion.get("artist"),
        "album": datos_cancion.get("album"),
    })


def _identificar_con_audd(audio_base64, api_key):
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


def _respuesta(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data),
    }
