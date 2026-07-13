"""
Endpoint: /api/buscar
Recibe título + artista, busca "acordes/tablatura" en Google Custom Search,
y elige el mejor resultado usando una heurística de prioridades por sitio.
"""

import json
import os
import urllib.request
import urllib.parse


# Sitios de acordes/tablaturas conocidos, ordenados por prioridad.
# Cuanto más alto el puntaje, más se prefiere ese sitio.
SITIOS_PRIORIDAD = {
    "lacuerda.net": 10,
    "cifraclub.com": 7,
    "cifraclub.com.br": 7,
    "ultimate-guitar.com": 6,
    "chordu.com": 4,
    "songsterr.com": 4,
}

# Sitios que casi nunca tienen la tablatura en sí (descartar)
SITIOS_DESCARTAR = [
    "youtube.com",
    "youtu.be",
    "pinterest.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
]

PALABRAS_CLAVE_BONUS = ["acordes", "tablatura", "tab", "chords"]


def handler(request):
    if request.get("method") != "POST":
        return _respuesta(405, {"error": "Método no permitido"})

    try:
        body = json.loads(request.get("body", "{}"))
    except json.JSONDecodeError:
        return _respuesta(400, {"error": "Body inválido"})

    titulo = body.get("titulo")
    artista = body.get("artista")
    if not titulo or not artista:
        return _respuesta(400, {"error": "Falta título o artista"})

    api_key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")
    if not api_key or not cx:
        return _respuesta(500, {"error": "Falta configurar GOOGLE_API_KEY o GOOGLE_CX"})

    consulta = f'"{titulo}" "{artista}" acordes tablatura'

    try:
        resultados = _buscar_en_google(consulta, api_key, cx)
    except Exception as e:
        return _respuesta(500, {"error": f"Error llamando a Google: {str(e)}"})

    if not resultados:
        return _respuesta(200, {"encontrado": False})

    opciones = _puntuar_y_ordenar(resultados)
    if not opciones:
        return _respuesta(200, {"encontrado": False})

    return _respuesta(200, {
        "encontrado": True,
        "opciones": opciones,
    })


def _buscar_en_google(consulta, api_key, cx):
    """Llama a Google Custom Search API y devuelve una lista simple de resultados."""
    params = urllib.parse.urlencode({
        "key": api_key,
        "cx": cx,
        "q": consulta,
        "num": 8,
    })
    url = f"https://www.googleapis.com/customsearch/v1?{params}"

    with urllib.request.urlopen(url, timeout=15) as respuesta:
        data = json.loads(respuesta.read().decode("utf-8"))

    items = data.get("items", [])
    return [
        {
            "titulo": item.get("title", ""),
            "url": item.get("link", ""),
            "descripcion": item.get("snippet", ""),
        }
        for item in items
    ]


def _puntuar_y_ordenar(resultados):
    """
    Heurística: le da un puntaje de 0 a 5 "estrellas" a cada resultado
    (no es un rating real de usuarios, es una estimación de confiabilidad
    de la fuente según el sitio y las palabras clave del título).
    Devuelve la lista ordenada de mejor a peor, sin los descartados.
    """
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
                break  # solo cuenta un sitio conocido, no acumular varios

        for palabra in PALABRAS_CLAVE_BONUS:
            if palabra in titulo_lower:
                puntaje_crudo += 2

        estrellas = _a_estrellas(puntaje_crudo)

        puntuados.append({
            "titulo": r["titulo"],
            "url": r["url"],
            "descripcion": r["descripcion"],
            "estrellas": estrellas,
        })

    puntuados.sort(key=lambda x: x["estrellas"], reverse=True)
    return puntuados


def _a_estrellas(puntaje_crudo):
    """Convierte el puntaje crudo de la heurística a una escala de 0 a 5."""
    # El puntaje crudo máximo posible ronda 10 (sitio conocido) + 2 (palabra clave) = 12
    PUNTAJE_MAXIMO = 12
    estrellas = round((puntaje_crudo / PUNTAJE_MAXIMO) * 5)
    return max(0, min(5, estrellas))


def _respuesta(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data),
    }
