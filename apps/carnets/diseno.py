"""Diseño de plantillas de carnet: conversión entre layout (JSON) y PPTX.

El editor web trabaja con una estructura JSON sencilla (coordenadas en
puntos). Este módulo la convierte a `.pptx` y viceversa usando `python-pptx`,
manteniendo la compatibilidad con el formato que consume `siglas.py`.

Convenciones del layout::

    {
      "ancho": 447.0, "alto": 696.5,
      "paginas": [
        {"nombre": "Anverso", "elementos": [
            {"tipo": "fondo",  "src": "lib:...", "x": 0, "y": 0,
             "w": 447, "h": 696.5, "rot": 0},
            {"tipo": "imagen", "src": "lib:a_RIF-G.png", "x":.., "marca": null},
            {"tipo": "imagen", "src": "lib:...", "marca": "foto"},
            {"tipo": "texto",  "marca": "nombre", "x":.., "sz": 24,
             "bold": false, "familia": "Georama Black", "algn": "ctr"}
        ]}
      ]
    }

`src` puede ser:
- ``lib:nombre.png``      → un elemento de la carpeta `img/`
- ``data:image/png;base64,...`` → imagen incrustada
- una ruta absoluta o relativa a MEDIA_ROOT
"""

import base64
import hashlib
import io
import mimetypes
from pathlib import Path

from django.conf import settings
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

EMU_POR_PT = 12700
INS_DEFAULT = 91425  # margen interno por defecto de las cajas de texto

LIBRERIA_DIR = Path(settings.BASE_DIR) / 'img'

_ALGN_A_PPTX = {
    'l': PP_ALIGN.LEFT,
    'ctr': PP_ALIGN.CENTER,
    'r': PP_ALIGN.RIGHT,
    'just': PP_ALIGN.JUSTIFY,
}
_ALGN_DESDE_PPTX = {
    PP_ALIGN.LEFT: 'l',
    PP_ALIGN.CENTER: 'ctr',
    PP_ALIGN.RIGHT: 'r',
    PP_ALIGN.JUSTIFY: 'just',
    None: 'l',
}

# Imagen usada para crear los marcadores de imagen (foto/QR) en el PPTX.
_PLACEHOLDER_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8'
    'zwAAAgcBApocMXEAAAAASUVORK5CYII=')


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _pt(emu):
    return round(emu / EMU_POR_PT, 2)


def _emu(pt):
    return Emu(int(round(float(pt) * EMU_POR_PT)))


def _mime(nombre):
    return mimetypes.guess_type(str(nombre))[0] or 'image/png'


def _data_uri(blob, mime=None):
    return 'data:%s;base64,%s' % (
        mime or 'image/png', base64.b64encode(blob).decode('ascii'))


def _bytes_de_src(src):
    """Devuelve (bytes, nombre_sugerido) para un `src` del layout."""
    if not src:
        return None, None
    if src.startswith('data:'):
        cabecera, _, datos = src.partition(',')
        return base64.b64decode(datos), 'imagen.png'
    if src.startswith('lib:'):
        ruta = LIBRERIA_DIR / src[4:]
        return ruta.read_bytes(), ruta.name
    ruta = Path(src)
    if not ruta.is_absolute():
        ruta = Path(settings.MEDIA_ROOT) / src
    return ruta.read_bytes(), ruta.name


def _blob_a_src(blob, nombre_sugerido='imagen.png'):
    """Convierte bytes a un `src` del layout (referencia a la librería o data URI)."""
    digest = hashlib.md5(blob).hexdigest()
    for archivo in libreria_archivos():
        if hashlib.md5(archivo.read_bytes()).hexdigest() == digest:
            return 'lib:' + archivo.name
    return _data_uri(blob, _mime(nombre_sugerido))


# ---------------------------------------------------------------------------
# Librería de elementos (carpeta img/)
# ---------------------------------------------------------------------------

def libreria_archivos():
    if not LIBRERIA_DIR.exists():
        return []
    return sorted(LIBRERIA_DIR.glob('*.png')) + sorted(LIBRERIA_DIR.glob('*.jpg'))


def libreria():
    """Lista de elementos disponibles para arrastrar al lienzo."""
    elementos = []
    for archivo in libreria_archivos():
        try:
            from django.urls import reverse
            url = reverse('carnets:libreria_elemento', args=[archivo.name])
        except Exception:
            url = '/libreria/%s/' % archivo.name
        elementos.append({'nombre': archivo.name, 'url': url})
    return elementos


# ---------------------------------------------------------------------------
# Lectura: PPTX → layout
# ---------------------------------------------------------------------------

def _descr_de(shape):
    try:
        return shape._element.nvPicPr.cNvPr.get('descr') or ''
    except Exception:
        pass
    try:
        return shape._element.nvSpPr.cNvPr.get('descr') or ''
    except Exception:
        return ''


def _marca(texto):
    if texto and '{{' in texto:
        return texto.replace('{', '').replace('}', '').strip()
    return None


def _elemento_desde_shape(shape):
    x, y = _pt(shape.left), _pt(shape.top)
    w, h = _pt(shape.width), _pt(shape.height)
    rot = round(float(shape.rotation or 0), 1)
    base = {'x': x, 'y': y, 'w': w, 'h': h, 'rot': rot}

    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        descr = _descr_de(shape)
        try:
            blob = shape.image.blob
            ext = shape.image.ext
        except Exception:
            return None
        if descr == '__fondo__':
            return dict(base, tipo='fondo', src=_blob_a_src(blob))
        marca = _marca(descr)
        return dict(base, tipo='imagen', marca=marca,
                    src=_blob_a_src(blob, 'imagen.%s' % ext))

    if shape.has_text_frame:
        texto = shape.text_frame.text or ''
        marca = _marca(texto)
        if not marca:
            return None
        run = None
        for par in shape.text_frame.paragraphs:
            if par.runs:
                run = par.runs[0]
                algn = _ALGN_DESDE_PPTX.get(par.alignment, 'l')
                break
        else:
            algn = 'l'
        sz = (run.font.size.pt if run and run.font.size else 18.0)
        bold = bool(run.font.bold) if run else False
        familia = (run.font.name if run and run.font.name else 'Georama')
        el = dict(base, tipo='texto', marca=marca, sz=sz, bold=bold,
                  familia=familia, algn=algn)
        descr = _descr_de(shape)
        if descr.startswith('__asset__:'):
            el['asset'] = descr[len('__asset__:'):]
        return el

    return None


def _fondo_bg(slide):
    """Lee el fondo declarado como `p:bg` (si lo hay) y lo devuelve como fondo."""
    try:
        blips = slide._element.xpath('.//p:cSld/p:bg//a:blip')
    except Exception:
        return None
    if not blips:
        return None
    rid = blips[0].get(qn('r:embed'))
    if not rid:
        return None
    try:
        parte = slide.part.related_part(rid)
        return _blob_a_src(parte.blob)
    except Exception:
        return None


def plantilla_a_layout(ruta):
    """Parsea un `.pptx` y devuelve el layout JSON editable."""
    prs = Presentation(str(ruta))
    layout = {
        'ancho': _pt(prs.slide_width),
        'alto': _pt(prs.slide_height),
        'paginas': [],
    }
    for indice, slide in enumerate(prs.slides, start=1):
        elementos = []
        fondo = _fondo_bg(slide)
        if fondo:
            elementos.append({'tipo': 'fondo', 'src': fondo, 'x': 0, 'y': 0,
                              'w': layout['ancho'], 'h': layout['alto'], 'rot': 0})
        for shape in slide.shapes:
            el = _elemento_desde_shape(shape)
            if el and el.get('marca') and el.get('tipo') == 'imagen':
                el['src'] = None  # marcador dinámico: su contenido se genera al renderizar
            if el:
                elementos.append(el)
        layout['paginas'].append({
            'nombre': 'Cara %d' % indice,
            'elementos': elementos,
        })
    return layout


# ---------------------------------------------------------------------------
# Escritura: layout → PPTX
# ---------------------------------------------------------------------------

def _agregar_imagen(slide, el):
    blob, nombre = _bytes_de_src(el.get('src'))
    if blob is None:
        if not el.get('marca'):
            return None
        blob = _PLACEHOLDER_PNG
    pic = slide.shapes.add_picture(
        io.BytesIO(blob), _emu(el.get('x', 0)), _emu(el.get('y', 0)),
        _emu(el.get('w', 10)), _emu(el.get('h', 10)))
    if el.get('tipo') == 'fondo':
        descr = '__fondo__'
    elif el.get('marca'):
        descr = '{{%s}}' % el['marca']
    else:
        descr = el.get('src', '')
    pic._element.nvPicPr.cNvPr.set('descr', descr)
    if el.get('rot'):
        pic.rotation = float(el['rot'])
    return pic


def _agregar_texto(slide, el):
    caja = slide.shapes.add_textbox(
        _emu(el.get('x', 0)), _emu(el.get('y', 0)),
        _emu(el.get('w', 100)), _emu(el.get('h', 30)))
    caja.rotation = float(el.get('rot') or 0)
    tf = caja.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(INS_DEFAULT)
    tf.margin_right = Emu(INS_DEFAULT)
    tf.margin_top = Emu(INS_DEFAULT)
    tf.margin_bottom = Emu(INS_DEFAULT)
    tf.vertical_anchor = MSO_ANCHOR.TOP

    par = tf.paragraphs[0]
    par.alignment = _ALGN_A_PPTX.get(el.get('algn', 'l'), PP_ALIGN.LEFT)
    run = par.add_run()
    run.text = '{{%s}}' % el.get('marca', 'texto')
    fuente = run.font
    fuente.size = Pt(float(el.get('sz', 18)))
    fuente.bold = bool(el.get('bold'))
    if el.get('familia'):
        fuente.name = el['familia']
    if el.get('asset'):
        # Enlace del marcador con un asset: se guarda en el descr de la forma
        # (lo lee `siglas._cargar_plantilla` al renderizar el PDF).
        caja._element.nvSpPr.cNvPr.set('descr', '__asset__:%s' % el['asset'])
    return caja


def layout_a_pptx(layout, destino=None):
    """Convierte un layout JSON en un archivo `.pptx`.

    Si `destino` es None devuelve los bytes; si es una ruta, escribe el archivo
    y devuelve la ruta.
    """
    prs = Presentation()
    prs.slide_width = _emu(layout.get('ancho', 447.0))
    prs.slide_height = _emu(layout.get('alto', 696.5))
    en_blanco = prs.slide_layouts[6]

    for pagina in layout.get('paginas', []):
        slide = prs.slides.add_slide(en_blanco)
        for el in pagina.get('elementos', []):
            tipo = el.get('tipo')
            if tipo in ('fondo', 'imagen'):
                _agregar_imagen(slide, el)
            elif tipo == 'texto':
                _agregar_texto(slide, el)

    if destino is None:
        buf = io.BytesIO()
        prs.save(buf)
        return buf.getvalue()
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(destino))
    return str(destino)


def marcador_imagen(marca, x, y, w, h):
    """Elemento de imagen dinámica (foto / QR) para usar en un layout."""
    return {'tipo': 'imagen', 'marca': marca, 'src': None,
            'x': x, 'y': y, 'w': w, 'h': h, 'rot': 0}