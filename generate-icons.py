#!/usr/bin/env python3
"""
Script para convertir icono.svg a PNG en dos tamaños
Requiere: pip install cairosvg pillow
"""

try:
    import cairosvg
    from PIL import Image
    import io
    import base64
    
    # Leer el SVG
    with open('public/icono.svg', 'r') as f:
        svg_content = f.read()
    
    # Convertir a PNG 192x192
    png_192 = io.BytesIO()
    cairosvg.svg2png(bytestring=svg_content.encode('utf-8'), write_to=png_192, output_width=192, output_height=192)
    png_192.seek(0)
    
    # Convertir a PNG 512x512
    png_512 = io.BytesIO()
    cairosvg.svg2png(bytestring=svg_content.encode('utf-8'), write_to=png_512, output_width=512, output_height=512)
    png_512.seek(0)
    
    # Guardar archivos
    with open('public/iconos/icono-192.png', 'wb') as f:
        f.write(png_192.read())
    
    png_512.seek(0)
    with open('public/iconos/icono-512.png', 'wb') as f:
        f.write(png_512.read())
    
    print("✅ Iconos creados exitosamente!")
    print("📁 public/iconos/icono-192.png")
    print("📁 public/iconos/icono-512.png")

except ImportError:
    print("❌ Falta instalar dependencias:")
    print("pip install cairosvg pillow")
except Exception as e:
    print(f"❌ Error: {e}")
