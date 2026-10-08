"""Integración con la BD y la web de SIGLAS + generación del PDF del carnet.

Flujo:
1. Consulta el funcionario por cédula en la base de datos PostgreSQL de SIGLAS.
2. Descarga la foto desde la web de SIGLAS con el patrón de URL configurado.
3. Rellena la plantilla credencialfundacion.pptx (marcadores {{...}}) y genera
   el PDF con reportlab, reutilizando las imágenes de fondo, coordenadas y
   tipografías (Georama) definidas en la propia plantilla.
"""

import io
import posixpath
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

import psycopg2
import qrcode
import requests
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

CONSULTA_FUNCIONARIO = """
SELECT f.ci, f.primer_nombre, f.segundo_nombre, f.primer_apellido, f.segundo_apellido,
       ct.nombre AS cargo, u.nombre AS departamento, foto.ruta AS foto_ruta,
       ic.tipo_sangre
FROM funcionarios.funcionario f
INNER JOIN funcionarios.funcionario_cargo fc
        ON f.id = fc.funcionario_id AND fc.status = 'A'
INNER JOIN organigrama.cargo c
        ON fc.cargo_id = c.id AND c.status = 'O'
INNER JOIN organigrama.cargo_tipo ct
        ON c.cargo_tipo_id = ct.id
INNER JOIN organigrama.unidad u
        ON c.unidad_funcional_id = u.id AND u.status = 'A'
LEFT JOIN funcionarios.foto foto
        ON f.id = foto.funcionario_id AND foto.status = 'A'
LEFT JOIN funcionarios.informacion_corporal ic
        ON f.id = ic.funcionario_id
WHERE f.ci = %s AND f.status = 'A';
"""

NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
}
_EMBED = ('{http://schemas.openxmlformats.org/officeDocument/2006/'
          'relationships}embed')
EMU_POR_PT = 12700.0
INS_DEFAULT = 91425  # margen interno de las cajas de texto de PowerPoint

_FUENTES_REGISTRADAS = False


def _registrar_fuentes():
    global _FUENTES_REGISTRADAS
    if _FUENTES_REGISTRADAS:
        return
    base = Path(__file__).resolve().parent / 'fonts'
    pdfmetrics.registerFont(TTFont('Georama', str(base / 'Georama-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('Georama-Bold', str(base / 'Georama-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('GeoramaBlack', str(base / 'Georama-Black.ttf')))
    pdfmetrics.registerFontFamily('Georama', normal='Georama', bold='Georama-Bold')
    _FUENTES_REGISTRADAS = True


def _fuente_de(familia, bold):
    familia = (familia or 'Georama').lower()
    if 'black' in familia:
        return 'GeoramaBlack'
    return 'Georama-Bold' if bold else 'Georama'


# ---------------------------------------------------------------------------
# Consulta a la BD de SIGLAS
# ---------------------------------------------------------------------------

def buscar_funcionario(ci):
    """Consulta SIGLAS por cédula. Devuelve un dict o None si no existe."""
    conn = psycopg2.connect(**settings.SIGLAS_DB)
    try:
        with conn.cursor() as cur:
            cur.execute(CONSULTA_FUNCIONARIO, (int(ci),))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    primer_nombre = (row[1] or '').strip()
    segundo_nombre = (row[2] or '').strip()
    primer_apellido = (row[3] or '').strip()
    segundo_apellido = (row[4] or '').strip()
    nombres = f'{primer_nombre} {segundo_nombre}'.strip()
    apellidos = f'{primer_apellido} {segundo_apellido}'.strip()
    return {
        'ci': str(row[0]),
        'nombres': nombres,
        'apellidos': apellidos,
        'nombre_completo': f'{nombres} {apellidos}'.strip(),
        'cargo': (row[5] or '').strip(),
        'departamento': (row[6] or '').strip(),
        'foto_ruta': row[7],
        'tipo_sangre': row[8],
    }


# ---------------------------------------------------------------------------
# Foto desde la web de SIGLAS
# ---------------------------------------------------------------------------

def descargar_foto(ci):
    """Descarga la foto del funcionario desde la web de SIGLAS (bytes JPEG) o None."""
    url = settings.SIGLAS_FOTO_URL.format(ci=ci)
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException:
        return None
    if resp.status_code != 200 or not resp.content:
        return None
    try:
        Image.open(io.BytesIO(resp.content)).verify()
    except Exception:
        return None
    return resp.content


def _foto_cuadrada(foto_bytes, lado=500):
    """Recorta la foto a cuadrado (centrado arriba, donde está la cara)."""
    img = Image.open(io.BytesIO(foto_bytes)).convert('RGB')
    return ImageOps.fit(img, (lado, lado), method=Image.LANCZOS, centering=(0.5, 0.35))


def _foto_placeholder(ci):
    img = Image.new('RGB', (500, 500), (220, 224, 228))
    draw = ImageDraw.Draw(img)
    fuente = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 56)
    draw.text((250, 230), 'SIN FOTO', font=fuente, fill=(90, 96, 102), anchor='mm')
    fuente_ci = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
    draw.text((250, 310), str(ci), font=fuente_ci, fill=(90, 96, 102), anchor='mm')
    return img


# ---------------------------------------------------------------------------
# Lectura de la plantilla PPTX (fondos, coordenadas y marcadores)
# ---------------------------------------------------------------------------

def _caja_de(xfrm):
    off, ext = xfrm.find('a:off', NS), xfrm.find('a:ext', NS)
    if off is None or ext is None:
        return None
    return (int(off.get('x')), int(off.get('y')),
            int(ext.get('cx')), int(ext.get('cy')))


def _formato_de(p_el):
    rpr = p_el.find('a:r/a:rPr', NS)
    if rpr is None:
        rpr = p_el.find('a:endParaRPr', NS)
    sz, bold, familia = 18.0, False, 'Georama'
    if rpr is not None:
        if rpr.get('sz'):
            sz = int(rpr.get('sz')) / 100
        bold = rpr.get('b') == '1'
        latin = rpr.find('a:latin', NS)
        if latin is not None and latin.get('typeface'):
            familia = latin.get('typeface')
    ppr = p_el.find('a:pPr', NS)
    algn = ppr.get('algn', 'l') if ppr is not None else 'l'
    return sz, bold, familia, algn


def _margenes_de(body):
    if body is None:
        return {k: INS_DEFAULT for k in ('l', 'r', 't', 'b')}
    def val(attr):
        v = body.get(attr)
        return int(v) if v is not None else INS_DEFAULT
    return {'l': val('lIns'), 'r': val('rIns'), 't': val('tIns'), 'b': val('bIns')}


@lru_cache(maxsize=4)
def _cargar_plantilla(ruta):
    """Parsea el PPTX y devuelve tamaño, fondos, textos y imágenes por diapositiva."""
    with zipfile.ZipFile(ruta) as z:
        pres = ET.fromstring(z.read('ppt/presentation.xml'))
        sld = pres.find('p:sldSz', NS)
        ancho, alto = int(sld.get('cx')), int(sld.get('cy'))

        diapositivas = []
        for num in (1, 2):
            xml = ET.fromstring(z.read('ppt/slides/slide%d.xml' % num))
            rels = ET.fromstring(z.read('ppt/slides/_rels/slide%d.xml.rels' % num))
            relmap = {r.get('Id'): r.get('Target') for r in rels}

            def media(rid):
                destino = posixpath.normpath(
                    posixpath.join('ppt/slides', relmap[rid]))
                return z.read(destino)

            fondo = None
            bgpr = xml.find('p:cSld/p:bg/p:bgPr', NS)
            blip = bgpr.find('a:blipFill/a:blip', NS) if bgpr is not None else None
            if blip is None and bgpr is not None:
                blip = bgpr.find('.//a:blip', NS)
            if blip is not None:
                fondo = media(blip.get(_EMBED))

            arbol = xml.find('p:cSld/p:spTree', NS)
            textos, imagenes = [], []

            for sp in arbol.findall('p:sp', NS):
                xfrm = sp.find('p:spPr/a:xfrm', NS)
                caja = _caja_de(xfrm) if xfrm is not None else None
                if caja is None:
                    continue
                body = sp.find('p:txBody/a:bodyPr', NS)
                for p_el in sp.findall('p:txBody/a:p', NS):
                    texto = ''.join(t.text or '' for t in p_el.iter(
                        '{%s}t' % NS['a']))
                    if '{{' not in texto:
                        continue
                    marca = texto.replace('{', '').replace('}', '').strip()
                    sz, bold, familia, algn = _formato_de(p_el)
                    textos.append({
                        'marca': marca, 'caja': caja, 'sz': sz, 'bold': bold,
                        'familia': familia, 'algn': algn,
                        'margenes': _margenes_de(body),
                    })

            for pic in arbol.findall('p:pic', NS):
                cnv = pic.find('p:nvPicPr/p:cNvPr', NS)
                descr = (cnv.get('descr') or '') if cnv is not None else ''
                if '{{' not in descr:
                    continue
                caja = _caja_de(pic.find('p:spPr/a:xfrm', NS))
                if caja is None:
                    continue
                blip = pic.find('p:blipFill/a:blip', NS)
                imagenes.append({
                    'marca': descr.replace('{', '').replace('}', '').strip(),
                    'caja': caja,
                    'bytes': media(blip.get(_EMBED)),
                })

            diapositivas.append({'fondo': fondo, 'textos': textos,
                                 'imagenes': imagenes})

    return {'ancho': ancho, 'alto': alto, 'diapositivas': diapositivas}


# ---------------------------------------------------------------------------
# Render del PDF
# ---------------------------------------------------------------------------

def _partir_lineas(texto, fuente, tam, ancho):
    lineas = []
    for salto in str(texto).split('\n'):
        palabras, actual = salto.split(), ''
        for palabra in palabras:
            cand = (actual + ' ' + palabra).strip()
            if not actual or pdfmetrics.stringWidth(cand, fuente, tam) <= ancho:
                actual = cand
            else:
                lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas or ['']


def _dibujar_texto(c, texto, caja_pt, cfg, alto_pagina):
    x, y_bottom, w, h = caja_pt
    y_top = y_bottom + h
    m = cfg['margenes']
    l, r, t, b = (m['l'] / EMU_POR_PT, m['r'] / EMU_POR_PT,
                  m['t'] / EMU_POR_PT, m['b'] / EMU_POR_PT)
    ancho_util = max(w - l - r, 10)
    fuente = _fuente_de(cfg['familia'], cfg['bold'])

    tam = cfg['sz']
    while tam > 8:
        lineas = _partir_lineas(texto, fuente, tam, ancho_util)
        if t + b + tam * 1.2 * len(lineas) <= h:
            break
        tam -= 0.5
    lineas = _partir_lineas(texto, fuente, tam, ancho_util)
    leading = tam * 1.2

    c.setFont(fuente, tam)
    try:
        ascent = pdfmetrics.getAscent(fuente, tam) or tam * 0.8
    except Exception:
        ascent = tam * 0.8
    y = y_top - t - ascent
    for i, linea in enumerate(lineas):
        yy = y - i * leading
        if cfg['algn'] == 'ctr':
            c.drawCentredString(x + w / 2, yy, linea)
        elif cfg['algn'] == 'r':
            c.drawRightString(x + w - r, yy, linea)
        else:
            c.drawString(x + l, yy, linea)


def _rect(c, caja_emu, alto_pagina):
    x, y, w, h = caja_emu
    return (x / EMU_POR_PT, alto_pagina - (y + h) / EMU_POR_PT,
            w / EMU_POR_PT, h / EMU_POR_PT)


def _dibujar_pagina(c, diapositiva, alto_pagina, ancho_pagina, valores, fotos):
    if diapositiva['fondo']:
        c.drawImage(ImageReader(io.BytesIO(diapositiva['fondo'])), 0, 0,
                    width=ancho_pagina, height=alto_pagina)
    for img in diapositiva['imagenes']:
        contenido = fotos.get(img['marca'])
        if contenido is None:
            continue
        x, y, w, h = _rect(c, img['caja'], alto_pagina)
        c.drawImage(ImageReader(contenido), x, y, width=w, height=h,
                    mask='auto')
    for cfg in diapositiva['textos']:
        contenido = valores.get(cfg['marca'])
        if contenido is None:
            continue
        _dibujar_texto(c, contenido, _rect(c, cfg['caja'], alto_pagina),
                       cfg, alto_pagina)


def _qr_bytes(contenido):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(contenido)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def _ruta_plantilla_activa():
    """Devuelve la ruta del PPTX activo (si existe) o la plantilla por defecto."""
    try:
        from .models import Plantilla
        plantilla = Plantilla.objects.filter(
            activa=True, archivo__isnull=False,
        ).exclude(archivo='').order_by('-id').first()
        if plantilla:
            ruta = plantilla.archivo.path
            if Path(ruta).exists():
                return Path(ruta)
    except Exception:
        pass
    return Path(settings.PLANTILLA_CARNET)


def render_pdf(campos, foto=None, qr_texto=None, plantilla_ruta=None, titulo=None):
    """Genera el PDF del carnet (anverso + dorso) a partir de `campos`.

    campos: dict con claves 'nombre', 'cargo', 'documento' (y opcionalmente
    'razon_social', 'telefono', 'correo' provenientes de la plantilla activa).
    foto: bytes (JPEG/PNG) o None → se usa el placeholder "SIN FOTO".
    qr_texto: contenido del código QR. Si es None se usa el formato histórico.
    """
    _registrar_fuentes()
    ruta = Path(plantilla_ruta) if plantilla_ruta else _ruta_plantilla_activa()
    plantilla = _cargar_plantilla(str(ruta))
    ancho = plantilla['ancho'] / EMU_POR_PT
    alto = plantilla['alto'] / EMU_POR_PT

    ci = str(campos.get('documento', '')).strip()
    if foto:
        img = _foto_cuadrada(foto)
    else:
        img = _foto_placeholder(ci or '—')

    valores = {
        'nombre': campos.get('nombre') or '—',
        'cargo': campos.get('cargo') or '—',
        'documento': ci or '—',
        'razon_social': campos.get('razon_social') or '',
        'telefono': campos.get('telefono') or '',
        'correo': campos.get('correo') or '',
    }

    if qr_texto is None:
        qr_texto = 'CARNET\nCI: %s\n%s' % (
            ci, campos.get('nombre') or '')

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(ancho, alto))
    c.setTitle(titulo or 'Carnet %s - %s' % (ci, campos.get('nombre') or ''))

    diapos = plantilla['diapositivas']
    fotos_anverso = {'foto': img}
    _dibujar_pagina(c, diapos[0], alto, ancho, valores, fotos_anverso)
    c.showPage()

    fotos_dorso = {}
    for imagin in diapos[1]['imagenes']:
        if imagin['marca'] in ('code_qr', 'qr'):
            fotos_dorso[imagin['marca']] = _qr_bytes(qr_texto)
    _dibujar_pagina(c, diapos[1], alto, ancho, valores, fotos_dorso)
    c.showPage()

    c.save()
    return buf.getvalue()


def generar_pdf(ci):
    """Devuelve (datos, pdf_bytes). datos es None si la cédula no existe."""
    datos = buscar_funcionario(ci)
    if datos is None:
        return None, None

    foto = descargar_foto(ci)
    campos = {
        'nombre': datos['nombre_completo'],
        'cargo': datos['cargo'] or '—',
        'documento': datos['ci'],
    }
    pdf = render_pdf(campos, foto=foto,
                     titulo='Carnet %s - %s' % (datos['ci'], datos['nombre_completo']))
    return datos, pdf
