(function () {
  'use strict';

  const root = document.getElementById('editor');
  if (!root) return;

  const layout = JSON.parse(document.getElementById('layout-data').textContent);
  const libreria = JSON.parse(document.getElementById('libreria-data').textContent);
  const csrf = root.querySelector('input[name=csrfmiddlewaretoken]').value;

  const cfg = {
    guardar: root.dataset.guardarUrl,
    preview: root.dataset.previewUrl,
    importar: root.dataset.importarUrl,
  };
  let pk = root.dataset.pk || '';

  const lienzo = document.getElementById('lienzo');
  const inspector = document.getElementById('inspector');
  const listaPaginas = document.getElementById('lista-paginas');
  const pagTitulo = document.getElementById('pagina-titulo');

  let paginaActual = 0;
  let seleccion = null;
  let zoom = 0.9;

  const urlLibreria = {};
  libreria.forEach(function (it) { urlLibreria[it.nombre] = it.url; });

  function srcResuelto(src) {
    if (!src) return '';
    if (src.indexOf('lib:') === 0) {
      const nombre = src.slice(4);
      return urlLibreria[nombre] || ('/libreria/' + nombre + '/');
    }
    return src;
  }

  function pagina() { return layout.paginas[paginaActual]; }
  function elementos() { return pagina().elementos; }
  function red(v) { return Math.round(v * 10) / 10; }

  // ------------------------------------------------------------------ render
  function renderTodo() { renderPaginas(); renderLienzo(); renderInspector(); }

  function renderPaginas() {
    listaPaginas.innerHTML = '';
    layout.paginas.forEach(function (pg, i) {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex align-items-center gap-2 py-2' +
        (i === paginaActual ? ' active' : '');

      const nombre = document.createElement('span');
      nombre.className = 'flex-fill text-truncate';
      nombre.textContent = pg.nombre;
      nombre.style.cursor = 'pointer';
      nombre.addEventListener('click', function () {
        paginaActual = i; seleccion = null; renderTodo();
      });

      function boton(icono, titulo, fn, clase) {
        const b = document.createElement('button');
        b.className = 'btn btn-sm btn-link p-0 ' + (clase || '');
        b.title = titulo;
        b.innerHTML = '<i class="bi bi-' + icono + '"></i>';
        b.addEventListener('click', function (e) { e.stopPropagation(); fn(); });
        return b;
      }

      li.appendChild(nombre);
      li.appendChild(boton('arrow-up', 'Subir', function () { moverPagina(i, -1); }));
      li.appendChild(boton('arrow-down', 'Bajar', function () { moverPagina(i, 1); }));
      li.appendChild(boton('pencil', 'Renombrar', function () {
        const n = prompt('Nombre de la página', pg.nombre);
        if (n) { pg.nombre = n; renderPaginas(); }
      }));
      li.appendChild(boton('trash', 'Eliminar', function () {
        if (layout.paginas.length <= 1) { alert('Debe quedar al menos una página.'); return; }
        if (!confirm('¿Eliminar la página "' + pg.nombre + '"?')) return;
        layout.paginas.splice(i, 1);
        paginaActual = Math.max(0, Math.min(paginaActual, layout.paginas.length - 1));
        seleccion = null; renderTodo();
      }, 'text-danger'));
      listaPaginas.appendChild(li);
    });
  }

  function renderLienzo() {
    pagTitulo.textContent = pagina().nombre;
    lienzo.innerHTML = '';
    lienzo.style.width = (layout.ancho * zoom) + 'px';
    lienzo.style.height = (layout.alto * zoom) + 'px';
    elementos().forEach(function (el) {
      const div = crearElemento(el);
      lienzo.appendChild(div);
      if (seleccion === el) {
        div.classList.add('seleccionado');
        agregarHandles(div, el);
      }
    });
  }

  function estiloTexto(nodo, el) {
    nodo.style.fontSize = (el.sz * zoom) + 'px';
    nodo.style.fontWeight = el.bold ? '700' : '400';
    nodo.style.fontFamily = 'system-ui, sans-serif';
    nodo.style.textAlign = el.algn === 'ctr' ? 'center' : (el.algn === 'r' ? 'right' : 'left');
    nodo.style.justifyContent = el.algn === 'ctr' ? 'center' : (el.algn === 'r' ? 'flex-end' : 'flex-start');
    nodo.style.lineHeight = '1.2';
    nodo.style.padding = (7.2 * zoom) + 'px';
  }

  function crearElemento(el) {
    const div = document.createElement('div');
    div.className = 'el' + (el.tipo === 'fondo' ? ' fondo' : '');
    div.style.left = (el.x * zoom) + 'px';
    div.style.top = (el.y * zoom) + 'px';
    div.style.width = (el.w * zoom) + 'px';
    div.style.height = (el.h * zoom) + 'px';
    if (el.rot) div.style.transform = 'rotate(' + el.rot + 'deg)';

    if (el.tipo === 'texto') {
      const t = document.createElement('div');
      t.className = 'el-texto';
      t.textContent = '{{' + el.marca + '}}';
      estiloTexto(t, el);
      div.appendChild(t);
    } else if (el.marca) {
      div.classList.add('el-marca');
      div.textContent = '{{' + el.marca + '}}';
    } else {
      const img = document.createElement('img');
      img.className = 'el-img';
      img.src = srcResuelto(el.src);
      img.alt = '';
      div.appendChild(img);
    }

    div.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      e.stopPropagation();
      seleccion = el;
      marcarSeleccion(div);
      renderInspector();
      iniciarArrastre(e, el, div);
    });
    return div;
  }

  function marcarSeleccion(divActual) {
    lienzo.querySelectorAll('.el').forEach(function (n) {
      n.classList.remove('seleccionado');
      n.querySelectorAll('.handle').forEach(function (h) { h.remove(); });
    });
    divActual.classList.add('seleccionado');
    agregarHandles(divActual, seleccion);
  }

  function agregarHandles(div, el) {
    ['nw', 'ne', 'sw', 'se'].forEach(function (pos) {
      const h = document.createElement('div');
      h.className = 'handle';
      h.style.left = (pos[1] === 'w' ? -6 : div.offsetWidth - 6) + 'px';
      h.style.top = (pos[0] === 'n' ? -6 : div.offsetHeight - 6) + 'px';
      h.style.cursor = pos + '-resize';
      h.addEventListener('mousedown', function (e) {
        e.stopPropagation();
        seleccion = el;
        iniciarRedimension(e, el, div, pos);
      });
      div.appendChild(h);
    });
  }

  // --------------------------------------------------------------- arrastres
  function iniciarArrastre(e, el, div) {
    e.preventDefault();
    const x0 = e.clientX, y0 = e.clientY, ex = el.x, ey = el.y;
    function mover(ev) {
      el.x = red(ex + (ev.clientX - x0) / zoom);
      el.y = red(ey + (ev.clientY - y0) / zoom);
      div.style.left = (el.x * zoom) + 'px';
      div.style.top = (el.y * zoom) + 'px';
      actualizarCoords();
    }
    function soltar() {
      document.removeEventListener('mousemove', mover);
      document.removeEventListener('mouseup', soltar);
    }
    document.addEventListener('mousemove', mover);
    document.addEventListener('mouseup', soltar);
  }

  function iniciarRedimension(e, el, div, pos) {
    e.preventDefault();
    const x0 = e.clientX, y0 = e.clientY, ex = el.x, ey = el.y, ew = el.w, eh = el.h;
    function redim(ev) {
      const dx = (ev.clientX - x0) / zoom, dy = (ev.clientY - y0) / zoom;
      let x = ex, y = ey, w = ew, h = eh;
      if (pos[1] === 'e') w = Math.max(5, ew + dx);
      if (pos[1] === 'w') { w = Math.max(5, ew - dx); x = ex + (ew - w); }
      if (pos[0] === 's') h = Math.max(5, eh + dy);
      if (pos[0] === 'n') { h = Math.max(5, eh - dy); y = ey + (eh - h); }
      el.x = red(x); el.y = red(y); el.w = red(w); el.h = red(h);
      div.style.left = (el.x * zoom) + 'px';
      div.style.top = (el.y * zoom) + 'px';
      div.style.width = (el.w * zoom) + 'px';
      div.style.height = (el.h * zoom) + 'px';
      actualizarCoords();
    }
    function soltar() {
      document.removeEventListener('mousemove', redim);
      document.removeEventListener('mouseup', soltar);
      renderLienzo();
    }
    document.addEventListener('mousemove', redim);
    document.addEventListener('mouseup', soltar);
  }

  // -------------------------------------------------------------- inspector
  function actualizarCoords() {
    if (!seleccion) return;
    inspector.querySelectorAll('[data-campo]').forEach(function (inp) {
      const c = inp.dataset.campo;
      if (['x', 'y', 'w', 'h'].indexOf(c) >= 0) inp.value = red(seleccion[c]);
    });
  }

  function agregarCampo(contenedor, etiqueta, input) {
    const d = document.createElement('div');
    d.className = 'mb-2';
    const l = document.createElement('label');
    l.className = 'form-label small mb-0';
    l.textContent = etiqueta;
    d.appendChild(l);
    d.appendChild(input);
    contenedor.appendChild(d);
  }

  function numInput(campo, valor, paso) {
    const i = document.createElement('input');
    i.type = 'number';
    i.step = paso || '0.1';
    i.className = 'form-control form-control-sm';
    i.dataset.campo = campo;
    i.value = red(valor);
    i.addEventListener('input', function () {
      if (!seleccion) return;
      seleccion[campo] = parseFloat(i.value) || 0;
    });
    i.addEventListener('change', function () { renderLienzo(); });
    return i;
  }

  function renderInspector() {
    inspector.innerHTML = '';
    if (!seleccion) {
      inspector.innerHTML = '<p class="text-muted small mb-0">Selecciona un elemento del lienzo.</p>';
      return;
    }
    const el = seleccion;

    const cab = document.createElement('div');
    cab.className = 'mb-2';
    const tipo = el.tipo === 'texto' ? 'Texto' : (el.tipo === 'fondo' ? 'Fondo' : 'Imagen');
    cab.innerHTML = '<span class="badge text-bg-secondary">' + tipo + '</span>' +
      (el.marca ? ' <span class="badge text-bg-info">{{' + el.marca + '}}</span>' : '');
    inspector.appendChild(cab);

    if (el.tipo === 'texto') {
      // --- Marca ---
      const marca = document.createElement('input');
      marca.type = 'text';
      marca.className = 'form-control form-control-sm';
      marca.value = el.marca || '';
      marca.addEventListener('input', function () { el.marca = marca.value.trim(); renderLienzo(); });
      agregarCampo(inspector, 'Marca', marca);

      // --- Asset (opcional): elige un asset de la librería para que se muestre al renderizar este marcador
      const assetLabel = document.createElement('div');
      assetLabel.className = 'mb-2';
      const assetLbl = document.createElement('label');
      assetLbl.className = 'form-label small mb-0';
      assetLbl.textContent = 'Asset (imagen opcional)';
      assetLabel.appendChild(assetLbl);

      const assetSelect = document.createElement('select');
      assetSelect.className = 'form-select form-select-sm';
      // opción "ninguno"
      const optNone = document.createElement('option');
      optNone.value = '';
      optNone.textContent = '(ninguno)';
      assetSelect.appendChild(optNone);
      // opciones de la librería
      libreria.forEach(function (it) {
        const opt = document.createElement('option');
        opt.value = 'lib:' + it.nombre;
        opt.textContent = it.nombre;
        if (el.asset === opt.value) opt.selected = true;
        assetSelect.appendChild(opt);
      });
      assetSelect.addEventListener('change', function () {
        el.asset = assetSelect.value; renderLienzo(); renderInspector();
      });
      assetLabel.appendChild(assetSelect);
      inspector.appendChild(assetLabel);

      const fila = document.createElement('div');
      fila.className = 'row g-1';
      [['x', 'X'], ['y', 'Y'], ['w', 'Ancho'], ['h', 'Alto']].forEach(function (par) {
        const col = document.createElement('div');
        col.className = 'col-6';
        agregarCampo(col, par[1], numInput(par[0], el[par[0]]));
        fila.appendChild(col);
      });
      inspector.appendChild(fila);

      const sz = numInput('sz', el.sz, '1');
      sz.addEventListener('input', function () { renderLienzo(); });
      agregarCampo(inspector, 'Tamaño (pt)', sz);

      const fam = document.createElement('select');
      fam.className = 'form-select form-select-sm';
      ['Georama', 'Georama Black'].forEach(function (f) {
        const o = document.createElement('option');
        o.value = f; o.textContent = f;
        if (el.familia === f) o.selected = true;
        fam.appendChild(o);
      });
      fam.addEventListener('change', function () { el.familia = fam.value; renderLienzo(); });
      agregarCampo(inspector, 'Fuente', fam);

      const algn = document.createElement('select');
      algn.className = 'form-select form-select-sm';
      [['l', 'Izquierda'], ['ctr', 'Centrado'], ['r', 'Derecha']].forEach(function (p) {
        const o = document.createElement('option');
        o.value = p[0]; o.textContent = p[1];
        if (el.algn === p[0]) o.selected = true;
        algn.appendChild(o);
      });
      algn.addEventListener('change', function () { el.algn = algn.value; renderLienzo(); });
      agregarCampo(inspector, 'Alineación', algn);

      const neg = document.createElement('div');
      neg.className = 'form-check';
      neg.innerHTML = '<input class="form-check-input" type="checkbox" id="chk-bold">' +
        '<label class="form-check-label small" for="chk-bold">Negrita</label>';
      const chk = neg.querySelector('input');
      chk.checked = !!el.bold;
      chk.addEventListener('change', function () { el.bold = chk.checked; renderLienzo(); });
      inspector.appendChild(neg);
    } else {
      if (el.marca) {
        const marca = document.createElement('input');
        marca.type = 'text';
        marca.className = 'form-control form-control-sm';
        marca.value = el.marca;
        marca.addEventListener('input', function () { el.marca = marca.value.trim(); renderLienzo(); });
        agregarCampo(inspector, 'Marca (foto / QR)', marca);
      }
      const fila = document.createElement('div');
      fila.className = 'row g-1';
      [['x', 'X'], ['y', 'Y'], ['w', 'Ancho'], ['h', 'Alto']].forEach(function (par) {
        const col = document.createElement('div');
        col.className = 'col-6';
        agregarCampo(col, par[1], numInput(par[0], el[par[0]]));
        fila.appendChild(col);
      });
      inspector.appendChild(fila);

      const rot = numInput('rot', el.rot || 0, '1');
      rot.addEventListener('input', function () { renderLienzo(); });
      agregarCampo(inspector, 'Rotación (°)', rot);
    }

    const acciones = document.createElement('div');
    acciones.className = 'd-grid gap-1 mt-2';
    acciones.innerHTML =
      '<button class="btn btn-sm btn-outline-secondary" id="el-frente">Traer al frente</button>' +
      '<button class="btn btn-sm btn-outline-secondary" id="el-fondo">Enviar al fondo</button>' +
      '<button class="btn btn-sm btn-outline-danger" id="el-borrar">Eliminar</button>';
    inspector.appendChild(acciones);

    acciones.querySelector('#el-frente').addEventListener('click', function () {
      const arr = elementos(); const i = arr.indexOf(el);
      arr.splice(i, 1); arr.push(el); renderLienzo();
    });
    acciones.querySelector('#el-fondo').addEventListener('click', function () {
      const arr = elementos(); const i = arr.indexOf(el);
      arr.splice(i, 1); arr.unshift(el); renderLienzo();
    });
    acciones.querySelector('#el-borrar').addEventListener('click', function () {
      const arr = elementos(); const i = arr.indexOf(el);
      arr.splice(i, 1); seleccion = null; renderTodo();
    });
  }

  // ------------------------------------------------------------- librería/UI
  function renderLibreria() {
    const cont = document.getElementById('libreria');
    cont.innerHTML = '';
    libreria.forEach(function (it) {
      const d = document.createElement('div');
      d.className = 'libreria-item';
      d.title = it.nombre;
      d.innerHTML = '<img src="' + it.url + '" alt=""><span>' + it.nombre + '</span>';
      d.addEventListener('click', function () { usarElemento('lib:' + it.nombre); });
      cont.appendChild(d);
    });
  }

  function usarElemento(src) {
    if (seleccion && seleccion.tipo === 'fondo') {
      seleccion.src = src; renderLienzo(); renderInspector(); return;
    }
    const img = new Image();
    img.onload = function () {
      const maxW = 160;
      const escala = Math.min(1, maxW / img.width);
      const w = Math.round(img.width * escala);
      const h = Math.round(img.height * escala);
      const el = { tipo: 'imagen', src: src, marca: null, rot: 0,
        x: red((layout.ancho - w) / 2), y: red((layout.alto - h) / 2), w: w, h: h };
      elementos().push(el);
      seleccion = el; renderTodo();
    };
    img.src = srcResuelto(src);
  }

  function fondoDesde(src) {
    let f = elementos().find(function (e) { return e.tipo === 'fondo'; });
    if (!f) {
      f = { tipo: 'fondo', src: src, x: 0, y: 0, w: layout.ancho, h: layout.alto, rot: 0 };
      elementos().unshift(f);
    } else {
      f.src = src;
    }
    renderLienzo();
  }

  document.getElementById('btn-add-pagina').addEventListener('click', function () {
    const n = prompt('Nombre de la nueva página', 'Cara ' + (layout.paginas.length + 1));
    if (!n) return;
    layout.paginas.push({ nombre: n, elementos: [] });
    paginaActual = layout.paginas.length - 1;
    seleccion = null; renderTodo();
  });

  document.getElementById('btn-add-texto').addEventListener('click', function () {
    const campo = document.getElementById('nueva-marca');
    let marca = (campo.value || '').trim().replace(/[{}]/g, '');
    if (!marca) { marca = prompt('Nombre de la marca', 'nombre'); if (!marca) return; }
    const el = { tipo: 'texto', marca: marca, x: 40, y: 40, w: 300, h: 36,
      sz: 18, bold: false, familia: 'Georama', algn: 'l', rot: 0 };
    elementos().push(el);
    seleccion = el; campo.value = ''; renderTodo();
  });

  document.getElementById('btn-add-foto').addEventListener('click', function () {
    const el = { tipo: 'imagen', marca: 'foto', src: null, x: 143, y: 213,
      w: 171, h: 171, rot: 0 };
    elementos().push(el); seleccion = el; renderTodo();
  });

  document.getElementById('btn-add-qr').addEventListener('click', function () {
    const el = { tipo: 'imagen', marca: 'code_qr', src: null, x: 171, y: 296,
      w: 105, h: 105, rot: 0 };
    elementos().push(el); seleccion = el; renderTodo();
  });

  document.getElementById('subir-elemento').addEventListener('change', function (e) {
    const file = e.target.files[0]; if (!file) return;
    const lector = new FileReader();
    lector.onload = function () { usarElemento(lector.result); e.target.value = ''; };
    lector.readAsDataURL(file);
  });

  document.getElementById('zoom-in').addEventListener('click', function () {
    zoom = Math.min(2, zoom + 0.1); renderLienzo();
  });
  document.getElementById('zoom-out').addEventListener('click', function () {
    zoom = Math.max(0.2, zoom - 0.1); renderLienzo();
  });
  document.getElementById('zoom-reset').addEventListener('click', function () {
    zoom = 0.9; renderLienzo();
  });

  document.addEventListener('keydown', function (e) {
    if (!seleccion) return;
    if (e.key === 'Delete' || e.key === 'Backspace') {
      const t = e.target.tagName;
      if (t === 'INPUT' || t === 'TEXTAREA' || t === 'SELECT') return;
      const arr = elementos(); const i = arr.indexOf(seleccion);
      if (i >= 0) { arr.splice(i, 1); seleccion = null; e.preventDefault(); renderTodo(); }
    }
  });

  // ------------------------------------------------------------------ red
  function metaCampos() {
    return {
      pk: pk || null,
      nombre: document.getElementById('meta-nombre').value.trim(),
      razon_social: document.getElementById('meta-razon').value.trim(),
      telefono: document.getElementById('meta-telefono').value.trim(),
      correo: document.getElementById('meta-correo').value.trim(),
      activa: document.getElementById('meta-activa').checked,
      layout: layout,
    };
  }

  function postJSON(url, cuerpo) {
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo),
    });
  }

  document.getElementById('btn-guardar').addEventListener('click', function () {
    const datos = metaCampos();
    if (!datos.nombre) { alert('Escribe un nombre para la plantilla.'); return; }
    postJSON(cfg.guardar, datos).then(function (r) {
      if (!r.ok) throw new Error('No se pudo guardar.');
      return r.json();
    }).then(function (res) {
      pk = res.pk; root.dataset.pk = pk;
      alert('Plantilla guardada correctamente.');
    }).catch(function (err) { alert(err.message); });
  });

  document.getElementById('btn-preview').addEventListener('click', function () {
    postJSON(cfg.preview, { layout: layout, campos: {} }).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error(t); });
      return r.blob();
    }).then(function (blob) {
      window.open(URL.createObjectURL(blob), '_blank');
    }).catch(function (err) { alert('No se pudo generar la vista previa: ' + err.message); });
  });

  document.getElementById('importar-archivo').addEventListener('change', function (e) {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData();
    fd.append('archivo', file);
    fetch(cfg.importar, { method: 'POST', headers: { 'X-CSRFToken': csrf }, body: fd })
      .then(function (r) {
        if (!r.ok) return r.text().then(function (t) { throw new Error(t); });
        return r.json();
      })
      .then(function (res) {
        layout.ancho = res.layout.ancho; layout.alto = res.layout.alto;
        layout.paginas = res.layout.paginas;
        paginaActual = 0; seleccion = null;
        document.getElementById('meta-nombre').value = file.name.replace(/\.pptx$/i, '');
        renderTodo();
        alert('PPTX importado. Revisa el diseño y guarda para conservarlo.');
      })
      .catch(function (err) { alert('No se pudo importar: ' + err.message); });
    e.target.value = '';
  });

  // Clic en el vacío del lienzo: quitar selección.
  lienzo.addEventListener('mousedown', function (e) {
    if (e.target === lienzo) { seleccion = null; renderLienzo(); renderInspector(); }
  });

  renderLibreria();
  renderTodo();

  // Autoescala inicial
  const wrap = document.getElementById('canvas-wrap');
  if (wrap && wrap.clientWidth) {
    zoom = Math.max(0.2, Math.min(1.2, (wrap.clientWidth - 40) / layout.ancho));
    renderLienzo();
  }
})();