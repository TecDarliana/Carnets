import io

import qrcode
from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1012, 638
TAMANO_FOTO = 220
FUENTES = '/usr/share/fonts/truetype/dejavu'

PRIMARIO = (13, 59, 102)
SECUNDARIO = (29, 120, 116)
TEXTO = (33, 37, 41)
MUTED = (108, 117, 125)


def _fuente(nombre, tamano):
    return ImageFont.truetype(f'{FUENTES}/{nombre}', tamano)


def _gradiente(draw, x0, y0, x1, y1, inicio, fin):
    ancho = x1 - x0
    for x in range(x0, x1):
        t = (x - x0) / max(ancho - 1, 1)
        color = tuple(int(inicio[i] + (fin[i] - inicio[i]) * t) for i in range(3))
        draw.line([(x, y0), (x, y1)], fill=color)


def _foto_circular(ruta, tamano):
    img = Image.open(ruta).convert('RGB')
    img.thumbnail((tamano * 2, tamano * 2))
    img = img.resize((tamano, tamano), Image.LANCZOS)
    mask = Image.new('L', (tamano, tamano), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, tamano - 1, tamano - 1), fill=255)
    circulo = Image.new('RGBA', (tamano, tamano), (0, 0, 0, 0))
    circulo.paste(img, (0, 0), mask)
    return circulo


def _texto_centrado(draw, texto, y, fuente, max_ancho, fill, min_tamano=26):
    f = fuente
    while draw.textlength(texto, font=f) > max_ancho and f.size > min_tamano:
        f = f.font_variant(size=f.size - 4)
    ancho = draw.textlength(texto, font=f)
    draw.text(((ANCHO - ancho) / 2, y), texto, font=f, fill=fill)


def generar_imagen_carnet(carnet):
    empleado = carnet.empleado
    lienzo = Image.new('RGB', (ANCHO, ALTO), 'white')
    draw = ImageDraw.Draw(lienzo)

    _gradiente(draw, 0, 0, ANCHO, 150, PRIMARIO, SECUNDARIO)
    draw.rectangle([0, 0, ANCHO - 1, ALTO - 1], outline=PRIMARIO, width=12)

    fuente_header = _fuente('DejaVuSans-Bold.ttf', 40)
    fuente_tipo = _fuente('DejaVuSans.ttf', 28)
    fuente_nombre = _fuente('DejaVuSans-Bold.ttf', 48)
    fuente_cargo = _fuente('DejaVuSans.ttf', 34)
    fuente_documento = _fuente('DejaVuSans-Bold.ttf', 30)
    fuente_footer = _fuente('DejaVuSans.ttf', 26)

    departamento = empleado.get_departamento_display().upper() or 'EMPRESA'
    _texto_centrado(draw, departamento, 22, fuente_header, ANCHO - 40, 'white')

    tipo = f'CARNET DE {carnet.get_tipo_display().upper()}'
    _texto_centrado(draw, tipo, 96, fuente_tipo, ANCHO - 40, 'white')

    cx = ANCHO // 2
    draw.ellipse([cx - TAMANO_FOTO // 2, 38, cx + TAMANO_FOTO // 2, 38 + TAMANO_FOTO],
                 outline='white', width=10)
    if empleado.foto:
        try:
            foto = _foto_circular(empleado.foto.path, TAMANO_FOTO)
            lienzo.paste(foto, (cx - TAMANO_FOTO // 2, 38), foto)
        except OSError:
            pass

    _texto_centrado(draw, empleado.nombre_completo.upper(), 292, fuente_nombre, ANCHO - 40, TEXTO)
    _texto_centrado(draw, empleado.get_cargo_display().upper(), 360, fuente_cargo, ANCHO - 40, MUTED)

    draw.line([48, 430, 340, 430], fill=PRIMARIO, width=6)

    documento = f'DOCUMENTO: {empleado.numero_documento}'
    _texto_centrado(draw, documento, 452, fuente_documento, 560, TEXTO)

    codigo = (
        f'CARNET:{carnet.numero}\n'
        f'CODIGO:{carnet.codigo}\n'
        f'NOMBRE:{empleado.nombre_completo}\n'
        f'DOCUMENTO:{empleado.numero_documento}'
    )
    qr = qrcode.make(codigo).convert('RGB').resize((200, 200), Image.LANCZOS)
    lienzo.paste(qr, (ANCHO - 200 - 48, 402))

    _texto_centrado(draw, f'N° {carnet.numero}', 528, fuente_footer, 560, MUTED)
    vencimiento = carnet.fecha_vencimiento.strftime('%d/%m/%Y') if carnet.fecha_vencimiento else 'SIN VENCIMIENTO'
    _texto_centrado(draw, f'VENCE: {vencimiento}', 566, fuente_footer, 560, MUTED)

    return lienzo


def imagen_carnet_png(carnet):
    buffer = io.BytesIO()
    generar_imagen_carnet(carnet).save(buffer, format='PNG')
    return buffer.getvalue()