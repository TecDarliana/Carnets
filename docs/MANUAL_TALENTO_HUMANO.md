# Sistema de Carnets — Manual de Procedimientos y Guía Operativa

Manual para Talento Humano y personal administrativo del sistema de generación
y resguardo de carnets. Versión Sprint 2 (almacenamiento MinIO + validación QR).

---

## 1. Descripción general

El sistema genera carnets en PDF con la plantilla institucional a partir de la
base de datos de personal (SIGLAS), los resguarda automáticamente en el
almacenamiento de objetos **MinIO** institucional y permite verificar su
vigencia escaneando el código QR impreso en el carnet.

Pantallas disponibles (según el rol):

| Pantalla | Qué se hace allí |
|---|---|
| **Carnets** (página principal) | Buscar funcionario por cédula, ver el carnet, crear carnets |
| **Historial** | Registro de cada carnet generado (fecha, cédula, usuario) |
| **Respaldo** | Catálogo de PDFs y fotos resguardados en MinIO, con descarga |
| **Empleados** | Personal activo con estado de carnet (✓ generado / ✗ pendiente) |
| **Plantillas** | Diseño del carnet (solo Gerente) |

---

## 2. Roles y permisos

| Rol | Puede | No puede |
|---|---|---|
| **Consultor** | Buscar por cédula, ver el carnet y el historial | Descargar/generar carnets, ver empleados |
| **Analista** | Todo lo anterior + generar carnets de empleados de la base de datos, ver Empleados y Respaldo | Crear carnets especiales (personas externas), tocar plantillas |
| **Gerente** | Todo: carnets especiales (externos), plantillas, empleados, historial y administrar usuarios | Eliminar registros del historial |
| **Administrador** | Todo lo anterior | Eliminar registros del historial (el historial es de solo lectura) |

Los usuarios se administran desde la sección **Usuarios** del menú
(disponible para *Gerente* y *Administrador*): crear usuarios, asignar rol,
cambiar contraseña y activar/desactivar. El administrador es el usuario con
la casilla *Súperusuario* activada.

---

## 3. Procedimientos operativos

### 3.1 Generar el carnet de un funcionario

1. Ingresar con usuario **Analista** o **Gerente**.
2. En la página principal escribir la **cédula** y pulsar *Buscar*.
3. Verificar los datos (foto, nombre, cargo, departamento).
4. Opciones:
   - **Vista previa**: ver el carnet sin generarlo.
   - **Descargar PDF**: genera el carnet, lo descarga y lo resguarda en MinIO.
   - Con el formulario bajo la tarjeta puede **corregir cualquier dato** antes
     de guardar; luego pulse *Guardar y editar antes de imprimir*.
5. El carnet queda registrado en el **Historial** y resguardado en **MinIO**.

### 3.2 Carnet de una persona fuera de la institución (especial)

Solo **Gerente**. En la página principal, pestaña **Manual (fuera de la
institución)**: completar nombre, documento, cargo, fecha de vencimiento
(opcional) y foto. Al imprimir, el QR apunta a la página de validación pública.

### 3.3 Generar carnets de todos los empleados pendientes

En **Empleados**, botón **Generar Todos los Carnets**: el sistema produce **un
solo PDF** con todos los carnets pendientes y lo descarga al equipo. Cada
carnet incluido queda registrado en el historial y el lote se resguarda en
MinIO (`carnets-personal/lotes/`). La tabla marca con **✓** a quienes ya
tienen carnet y con **✗** a los pendientes.

> ⚠️ Con varios cientos de empleados la generación tarda varios minutos
> (descarga cada foto). No cerrar la pestaña durante el proceso.

### 3.4 Historial de carnets generados

- Visible para todos los roles (Consultor incluido).
- **Solo el Administrador** puede eliminar registros (botón 🗑), útil para
  limpiar registros de pruebas. El borrado no afecta los archivos resguardados.

### 3.5 Respaldo (MinIO)

Pestaña **Respaldo**: catálogo de archivos en MinIO con filtros por tipo
(carnet / lote / foto) y origen (generado / histórico). Desde allí se puede
**Descargar** el archivo resguardado o **Reimprimir** un carnet individual con
los datos actuales. La descarga requiere rol Analista o superior.

### 3.6 Validación pública por QR

Al escanear el QR de un carnet con cualquier teléfono se abre una página
pública (sin login) con foto, datos y el sello de vigencia:

- **CARNET VIGENTE** (verde): funcionario activo o dentro de la fecha de
  vencimiento.
- **CARNET VENCIDO** (rojo): pasó la fecha de vencimiento indicada.
- **CARNET NO VIGENTE** (rojo): la persona ya no figura como funcionario
  activo.
- **VIGENCIA NO VERIFICABLE** (gris): no se pudo consultar la base de datos
  de personal en ese momento.

---

## 4. Resguardo en MinIO (aspectos técnicos)

### 4.1 Configuración

| Parámetro | Valor |
|---|---|
| Servidor MinIO | `http://172.17.9.90:9000` (VM debian-backup, Sede Fundación) |
| Bucket PDFs | `carnets-personal` |
| Bucket fotos | `fotoscarnets` |
| Credenciales | Variables `MINIO_*` del archivo `.env` (nunca en el repositorio) |

Convención de nombres (compatible con el sistema anterior):

| Archivo | Objeto en MinIO |
|---|---|
| Carnet PDF de un funcionario | `carnets-personal/Carnet_<cédula>.pdf` |
| Lote de "Generar Todos" | `carnets-personal/lotes/Carnets_lote_<fecha>.pdf` |
| Fotografía del funcionario | `fotoscarnets/<cédula>.jpg` |
| Históricos (réplica del sistema anterior) | `carnets-personal/historico/` y `fotoscarnets/historico/` |

### 4.2 Comportamiento ante fallas

El resguardo es de **mejor esfuerzo**: si MinIO no está disponible, la
generación de carnets, el historial y la validación QR **siguen funcionando**
con normalidad; el sistema registra el fallo en su bitácora e intentará
resguardar en la siguiente generación. En la pestaña Respaldo, la descarga de
un archivo no disponible muestra un mensaje de error en lugar de fallar.

---

## 5. Importación de carnets históricos

Los PDFs del sistema anterior viven en MinIO Cloud
(`https://minio.fundayacucho.gob.ve`). El proceso tiene dos pasos:

### Paso 1 — Réplica hacia el MinIO local (servidor con `mc`)

```bash
mc alias set minio_cloud https://minio.fundayacucho.gob.ve minioadmin 'CONTRASEÑA_CLOUD'
mc alias set localminio http://172.17.9.90:9000 minioadmin 'CONTRASEÑA_LOCAL'

# Sincronización de PDFs y fotos históricas hacia el almacenamiento local
mc mirror minio_cloud/carnets/ localminio/carnets-personal/historico/
mc mirror minio_cloud/fotoscarnets/ localminio/fotoscarnets/historico/
```

### Paso 2 — Indexación en la base de datos

Desde la carpeta del proyecto:

```bash
python manage.py carnets_importar_historico            # indexa y cataloga
python manage.py carnets_importar_historico --dry-run # solo lista lo que haría
```

El comando recorre los objetos bajo `historico/`, extrae la cédula del nombre
del archivo (ej. `Carnet_V12345678.pdf`, `foto_V12345678.jpg`), consulta los
datos actuales en SIGLAS y registra la entrada en el catálogo. Es
**idempotente**: puede ejecutarse varias veces sin duplicar (actualiza las
fechas/tamaños). Los históricos quedan visibles y descargables en la pestaña
**Respaldo** (filtro origen: *Histórico*).

---

## 6. Preguntas frecuentes

**Se generó un carnet pero no aparece en Respaldo.**
MinIO probablemente estaba inaccesible en ese momento. Vuelva a generar el
carnet (o pida reintentarlo) con el servidor disponible; el resguardo es
automático en cada generación.

**Un consultor necesita el PDF de un carnet.**
Debe solicitarse a un Analista/Gerente, o compartirse el enlace de validación
QR del carnet (página pública).

**El escaneo del QR muestra "VIGENCIA NO VERIFICABLE".**
La base de datos de personal (SIGLAS) no respondió. Reintentar más tarde; si
persiste, avisar al área de informática.
