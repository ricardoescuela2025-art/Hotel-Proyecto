from flask import Flask, render_template, request, redirect, session, flash
import pyodbc
import os
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secreto"

# Algunas habitaciones antiguas quedaron guardadas con nombres de archivo que
# ya no existen. Conservamos las imágenes cargadas por el usuario y mostramos
# la foto equivalente mientras se actualizan esos registros.
CARPETA_IMAGENES = os.path.join(app.static_folder, "img")
IMAGENES_REEMPLAZO = {
    "habitacion1.jpg": "hab-deluxe.jpg",
    "habitacion3.jpg": "h101.jpg",
}


def obtener_ruta_imagen(ruta_guardada):
    """Devuelve una ruta pública válida para una imagen de habitación."""
    if not ruta_guardada:
        return None

    nombre_archivo = os.path.basename(ruta_guardada)
    ruta_fisica = os.path.join(CARPETA_IMAGENES, nombre_archivo)
    if os.path.isfile(ruta_fisica):
        return f"/static/img/{nombre_archivo}"

    nombre_reemplazo = IMAGENES_REEMPLAZO.get(nombre_archivo)
    if nombre_reemplazo and os.path.isfile(os.path.join(CARPETA_IMAGENES, nombre_reemplazo)):
        return f"/static/img/{nombre_reemplazo}"

    return ruta_guardada

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "hotel_app.log")

handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

logger = logging.getLogger("hotel_app")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())
logger.propagate = False

logger.info("Sistema de logs inicializado para el proyecto Hotel")

@app.before_request
def registrar_peticion():
    logger.info("Solicitud %s %s", request.method, request.path)

@app.after_request
def registrar_respuesta(response):
    logger.info("Respuesta %s %s -> %s", request.method, request.path, response.status_code)
    return response

# ---------------- CONEXIÓN ---------------- #

def obtener_conexion():
    try:
        logger.debug("Intentando conectar a la base de datos...")
        return pyodbc.connect(
            "Driver={ODBC Driver 17 for SQL Server};"
            "Server=LAPTOP-54DLN69G\\SQLEXPRESS01;"
            "Database=ReservasHotel;"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
    except Exception as e:
        logger.exception("Error de conexión a la base de datos")
        return None

# Para rutas que usaban 'conectar()'
def conectar():
    return obtener_conexion()


# ----------------------------- LOGIN PAGE ----------------------------- #
@app.get("/")
def login():
    return render_template("login.html")

# ----------------------------- REGISTRO ----------------------------- #
@app.post("/registrar_usuario")
def registrar_usuario():
    nombre = request.form["nombre"]
    correo = request.form["correo"]
    password = request.form["password"]
    telefono = request.form["telefono"]

    logger.info("Intento de registro para %s", correo)
    conn = None
    cursor = None

    try:
        conn = obtener_conexion()

        if conn is None:
            raise Exception("No se pudo conectar a SQL Server")

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Usuarios (nombre, correo, contrasena, telefono, tipo)
            VALUES (?, ?, ?, ?, ?)
        """, (nombre, correo, password, telefono, "usuario"))

        conn.commit()

        flash("Usuario registrado correctamente", "success")
        return redirect("/")

    except pyodbc.IntegrityError as e:
        conn.rollback()
        logger.exception(e)
        flash(f"Error de integridad: {e}", "error")
        return redirect("/")

    except Exception as e:
        if conn:
            conn.rollback()

        logger.exception(e)
        print("ERROR SQL:", e)

        flash(str(e), "error")
        return redirect("/")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
# ----------------------------- LOGIN ----------------------------- #
@app.post("/login")
def iniciar_sesion():
    correo = request.form["usuario"]
    password = request.form["password"]

    logger.info("Intento de login para %s", correo)
    conn = obtener_conexion()

    if conn is None:
        logger.error("Login fallido por error de conexión: %s", correo)
        flash("No se pudo conectar a la base de datos", "error")
        return redirect("/")

    cursor = conn.cursor()
    cursor.execute(
    "SELECT id, nombre, tipo FROM Usuarios WHERE correo=? AND contrasena=?",
    (correo, password)
    
    )
    usuario_db = cursor.fetchone()
    conn.close()

    if usuario_db:
        session["id"] = usuario_db[0]
        session["nombre"] = usuario_db[1]
        session["tipo"] = usuario_db[2]
        logger.info("Login exitoso para %s (%s)", correo, usuario_db[2])

        if usuario_db[2] == "admin":
            return redirect("/admin/dashboard")
        elif usuario_db[2] == "recepcionista":
            return redirect("/recepcionista/home")
        else:
            return redirect("/habitaciones")
    else:
        logger.warning("Login fallido por credenciales incorrectas: %s", correo)
        flash("Credenciales incorrectas", "error")
        return redirect("/")

# ---------------- ADMIN ---------------- #
@app.get("/admin/dashboard")
def admin_dashboard():
    if session.get("tipo") != "admin":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM Reservas WHERE estado='activa'")
    total_reservas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='ocupada'")
    ocupadas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='disponible'")
    disponibles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones")
    total_habitaciones = cursor.fetchone()[0]

    cursor.execute("""
        SELECT 
            U.nombre,
            H.numero,
            R.fecha_entrada,
            R.fecha_salida,
            R.estado
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
    """)
    reservas = cursor.fetchall()

    cursor.execute("""
        SELECT TOP 4 nombre, correo, tipo 
        FROM Usuarios ORDER BY id DESC
    """)
    nuevos_usuarios = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        nombre=session["nombre"],
        total_reservas=total_reservas,
        ocupadas=ocupadas,
        disponibles=disponibles,
        total_habitaciones=total_habitaciones,
        reservas=reservas,
        nuevos_usuarios=nuevos_usuarios
    )


# ---------- USUARIOS ADMIN ---------- #
@app.get("/admin/usuarios")
def admin_listar_usuarios():
    if session.get("tipo") != "admin":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, correo, tipo FROM Usuarios ORDER BY id DESC")
    usuarios = cursor.fetchall()

    cursor.execute("SELECT TOP 4 id, nombre, correo, tipo FROM Usuarios ORDER BY id DESC")
    ultimos = cursor.fetchall()

    conn.close()
    return render_template("usuarios_list.html", usuarios=usuarios, ultimos_usuarios=ultimos)


@app.get("/admin/usuarios/nuevo")
def admin_nuevo_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")
    return render_template("usuario_form.html")


@app.post("/admin/usuarios/guardar")
def admin_guardar_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    nombre = request.form["nombre"]
    correo = request.form["correo"]
    contraseña = request.form["contraseña"]
    tipo = request.form["tipo"]

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Usuarios (nombre, correo, contraseña, tipo) VALUES (?,?,?,?)",
            (nombre, correo, contraseña, tipo),
        )
        conn.commit()
        flash("✔ Usuario agregado.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        conn.close()

    return redirect("/admin/usuarios")


@app.post("/admin/usuarios/eliminar")
def admin_eliminar_usuario():
    if session.get("tipo") != "admin":
        return redirect("/")

    usuario_id = request.form["usuario_id"]

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM Usuarios WHERE id = ?", (usuario_id,))
        conn.commit()

        flash("Usuario eliminado.", "success")

    except Exception as e:
        flash(f"Error: {e}", "error")

    finally:
        conn.close()

    return redirect("/admin/usuarios")


# ---------- HABITACIONES ADMIN ---------- #
@app.get("/admin/habitaciones")
def admin_listar_habitaciones():
    if session.get("tipo") != "admin":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT id, numero, tipo, precio, estado FROM Habitaciones ORDER BY id DESC")
    data = cursor.fetchall()
    conn.close()

    return render_template("habitaciones_list.html", habitaciones=data)


@app.get("/admin/habitaciones/nueva")
def admin_nueva_habitacion():
    if session.get("tipo") != "admin":
        return redirect("/")
    return render_template("habitacion_form.html")


@app.post("/admin/habitaciones/guardar")
def admin_guardar_habitacion():
    if session.get("tipo") != "admin":
        return redirect("/")

    numero = request.form["numero"]
    nombre = request.form["nombre"]
    tipo = request.form["tipo"]
    precio = request.form["precio"]
    estado = request.form["estado"]
    descripcion = request.form.get("descripcion", "")
    estrellas = request.form.get("estrellas", 0)

    # -----------------------------
    # 📸 FOTO
    # -----------------------------
    archivo = request.files["foto"]
    nombre_foto = secure_filename(archivo.filename)

    # Carpeta física REAL donde se guardará la foto
    ruta_carpeta = "static/img"
    os.makedirs(ruta_carpeta, exist_ok=True)

    # Guardar archivo físicamente
    ruta_fisica = os.path.join(ruta_carpeta, nombre_foto)
    archivo.save(ruta_fisica)

    # Ruta que se guardará en SQL (ruta pública)
    ruta_sql = f"/static/img/{nombre_foto}"

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Habitaciones
            (numero, nombre, tipo, precio, estado, descripcion, estrellas, imagen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (numero, nombre, tipo, precio, estado, descripcion, estrellas, ruta_sql))

        conn.commit()
        logger.info("Habitación agregada: número %s | tipo %s", numero, tipo)
        flash("✔ Habitación agregada.", "success")

    except Exception as e:
        logger.exception("Error al agregar habitación: %s", numero)
        flash(f"Error: {e}", "error")

    finally:
        conn.close()

    return redirect("/admin/habitaciones")




@app.post("/admin/habitaciones/eliminar")
def admin_eliminar_habitacion():
    if session.get("tipo") != "admin":
        return redirect("/")

    habitacion_id = request.form["habitacion_id"]

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM Habitaciones WHERE id = ?", (habitacion_id,))
        conn.commit()

        flash("✔ Habitación eliminada.", "success")

    except Exception as e:
        flash(f"Error: {e}", "error")

    finally:
        conn.close()

    return redirect("/admin/habitaciones")


# ---------- RESERVAS ADMIN ---------- #
@app.get("/admin/reservas")
def admin_listar_reservas():
    if session.get("tipo") != "admin":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT R.id, U.nombre, H.numero, R.fecha_entrada, R.fecha_salida, R.estado
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
    """)
    reservas = cursor.fetchall()
    conn.close()

    return render_template("reservas_list.html", reservas=reservas)


# ---------------- LOGOUT ---------------- #
@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RECEPCIONISTA ---------------- #
@app.get("/recepcionista/home")
def recepcionista_home():
    if session.get("tipo") != "recepcionista":
        return redirect("/")
    return render_template("recepcionista/home.html", nombre=session["nombre"])


@app.get("/recepcionista/reservar")
def recepcionista_reservar():
    if session.get("tipo") != "recepcionista":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, numero, tipo, precio
        FROM Habitaciones
        WHERE estado = 'Disponible' OR estado = 'disponible'
    """)
    habitaciones = cursor.fetchall()

    conn.close()

    return render_template(
        "recepcionista/crear_reserva.html",
        nombre=session.get("nombre", "Sin Nombre"),
        habitaciones=habitaciones
    )


@app.post("/recepcionista/reservar/guardar")
def recepcionista_guardar_reserva():
    if session.get("tipo") != "recepcionista":
        return redirect("/")

    usuario_id = request.form["usuario_id"]
    habitacion_id = request.form["habitacion_id"]
    fecha_entrada = request.form["fecha_entrada"]
    fecha_salida = request.form["fecha_salida"]

    logger.info("Creando reserva para usuario %s en habitación %s", usuario_id, habitacion_id)
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO Reservas (usuario_id, habitacion_id, fecha_entrada, fecha_salida, estado)
        VALUES (?,?,?,?, 'activa')
    """, (usuario_id, habitacion_id, fecha_entrada, fecha_salida))
    conn.commit()

    cursor.execute("UPDATE Habitaciones SET estado='ocupada' WHERE id=?", (habitacion_id,))
    conn.commit()

    conn.close()
    logger.info("Reserva creada correctamente para usuario %s", usuario_id)
    return redirect("/recepcionista/home")


@app.get("/recepcionista/reservas/lista")
def recepcionista_reservas_lista():
    if session.get("tipo") != "recepcionista":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT R.id, 
               U.nombre AS nombre_huesped, 
               H.numero AS habitacion_num, 
               R.fecha_entrada, 
               R.fecha_salida, 
               R.estado
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        ORDER BY R.id DESC
    """)
    reservas = cursor.fetchall()

    conn.close()

    return render_template(
        "recepcionista/reserva_list.html",
        nombre=session.get("nombre", "Sin Nombre"),
        reservas=reservas
    )


# ---------------- REPORTES RECEPCIONISTA ---------------- #
@app.get("/recepcionista/reportes")
def recepcionista_reportes():
    if session.get("tipo") != "recepcionista":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM Reservas")
    total_reservas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Reservas WHERE estado='activa'")
    reservas_activas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='ocupada'")
    ocupadas = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM Habitaciones
        WHERE estado='disponible' OR estado='Disponible'
    """)
    disponibles = cursor.fetchone()[0]

    cursor.execute("""
        SELECT SUM(H.precio)
        FROM Reservas R
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
    """)
    ingresos = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT TOP 10 
            R.id, 
            U.nombre, 
            H.numero, 
            R.fecha_entrada, 
            R.fecha_salida, 
            R.estado
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        ORDER BY R.id DESC
    """)
    ultimas_reservas = cursor.fetchall()

    conn.close()

    return render_template(
        "recepcionista/reportes.html",
        nombre=session.get("nombre", "Recepcionista"),
        total_reservas=total_reservas,
        reservas_activas=reservas_activas,
        ocupadas=ocupadas,
        disponibles=disponibles,
        ingresos=ingresos,
        ultimas_reservas=ultimas_reservas
    )


# ------------------------ API LLEGADAS ------------------------ #
@app.get("/api/llegadas")
def api_llegadas():
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            U.nombre AS huesped,
            H.tipo,
            CONVERT(varchar(5), CAST(R.fecha_entrada AS datetime), 108) AS hora_estimada,
            '---' AS hora_checkin
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        WHERE R.estado='activa'
    """)

    filas = cursor.fetchall()
    conn.close()

    data = []
    for f in filas:
        data.append({
            "guest": f[0],
            "roomType": f[1],
            "estimatedTime": f[2],
            "checkinTime": f[3]
        })

    return {"data": data}


@app.get("/api/salidas")
def api_salidas():
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            U.nombre AS huesped,
            H.tipo,
            CONVERT(varchar(5), CAST(R.fecha_salida AS datetime), 108) AS hora_estimada,
            '---' AS hora_checkout
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        WHERE R.estado = 'finalizada'
    """)

    filas = cursor.fetchall()
    conn.close()

    data = []
    for f in filas:
        data.append({
            "guest": f[0],
            "roomType": f[1],
            "estimatedTime": f[2],
            "checkoutTime": f[3]
        })

    return {"data": data}


# ------------------------ CHECK-IN PANEL (DUPLICADA PERO RESPETADA) ------------------------
# ------------------------ CHECK-IN PANEL (DISEÑO) ------------------------
@app.route('/recepcionista/checkin-panel')
def recepcionista_panel():

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nombre_cliente, tipo_habitacion, precio, codigo_reserva, dias
        FROM Reservas
        WHERE estado = 'Pendiente'
    """)
    reservas = cursor.fetchall()

    cursor.execute("""
        SELECT numero, estado
        FROM Habitaciones
        ORDER BY numero ASC
    """)
    habitaciones = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='Disponible'")
    disponibles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='Ocupada'")
    ocupadas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='Limpieza'")
    limpieza = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "recepcionista/crear_reservar.html",
        nombre=session.get("nombre", "Recepcionista"),
        reservas=reservas,
        habitaciones=habitaciones,
        disponibles=disponibles,
        ocupadas=ocupadas,
        limpieza=limpieza
    )

# ------------------------ CHECK-IN PANEL ------------------------
@app.get("/recepcionista/checkin")
def recepcionista_checkin():

    if session.get("tipo") != "recepcionista":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    # RESERVAS PENDIENTES DE CHECK-IN (estado = activa)
    cursor.execute("""
        SELECT 
            U.nombre AS nombre_cliente,
            H.tipo AS tipo_habitacion,
            H.precio,
            R.id AS codigo_reserva,
            DATEDIFF(DAY, R.fecha_entrada, R.fecha_salida) AS dias
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        WHERE R.estado = 'activa'
    """)
    reservas = cursor.fetchall()

    # TODAS LAS HABITACIONES CON SU ESTADO
    cursor.execute("SELECT numero, estado FROM Habitaciones ORDER BY numero ASC")
    habitaciones = cursor.fetchall()

    # CONTADORES
    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='disponible'")
    disponibles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='ocupada'")
    ocupadas = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='finalizada'")
    finalizadas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='mantenimiento'")
    limpieza = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "recepcionista/checkin.html",   # 👈 CORREGIDO
        nombre=session["nombre"],
        reservas=reservas,
        habitaciones=habitaciones,
        disponibles=disponibles,
        ocupadas=ocupadas,
        finalizadas=finalizadas,
        limpieza=limpieza
    )


# app.py (dentro de la función recepcionista_checkin)

# ------------------------ BÚSQUEDA DE RESERVAS ------------------------
@app.route('/buscar_reserva', methods=['GET'])
def buscar_reserva():
    palabra = request.args.get("q", "")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nombre_cliente, tipo_habitacion, precio, codigo_reserva, dias
        FROM Reservas
        WHERE nombre_cliente LIKE ? OR codigo_reserva LIKE ?
    """, ('%' + palabra + '%', '%' + palabra + '%'))

    resultados = cursor.fetchall()
    conn.close()

    return {"resultados": [list(r) for r in resultados]}


# ------------------------ FILTROS DE HABITACIONES ------------------------
@app.route('/filtrar_habitaciones/<estado>')
def filtrar_habs(estado):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT numero, estado
        FROM Habitaciones
        WHERE estado = ?
        ORDER BY numero ASC
    """, (estado.capitalize(),))

    habitaciones = cursor.fetchall()
    conn.close()

    return {"habitaciones": [list(h) for h in habitaciones]}


@app.get("/filtrar_habitaciones/<estado>")
def filtrar_habitaciones(estado):

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("SELECT numero, estado FROM Habitaciones WHERE estado = ?", estado)
    habitaciones = cursor.fetchall()
    conn.close()

    return {"habitaciones": habitaciones}
@app.get("/buscar_reserva2/<texto>")
def buscar_reserva2(texto):

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT U.nombre, H.tipo, H.precio, R.id, 
               DATEDIFF(DAY, R.fecha_entrada, R.fecha_salida)
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        WHERE (U.nombre LIKE ? OR R.id LIKE ?)
          AND R.estado='activa'
    """, ('%' + texto + '%', '%' + texto + '%'))

    reservas = cursor.fetchall()
    conn.close()

    return {"reservas": reservas}
@app.post("/recepcionista/checkin/ejecutar")
def ejecutar_checkin():
    data = request.get_json()

    reserva_id = data.get("reserva_id")
    habitacion_numero = data.get("habitacion_numero")

    if not reserva_id or not habitacion_numero:
        return {"success": False, "message": "Datos incompletos"}

    conn = obtener_conexion()
    cursor = conn.cursor()

    try:
        logger.info("Ejecutando check-in para reserva %s en habitación %s", reserva_id, habitacion_numero)
        cursor.execute("""
            UPDATE Reservas
            SET estado='finalizada'
            WHERE id=?
        """, reserva_id)

        cursor.execute("""
            UPDATE Habitaciones
            SET estado='finalizada'
            WHERE numero=?
        """, habitacion_numero)

        conn.commit()
        conn.close()
        logger.info("Check-in ejecutado correctamente para reserva %s", reserva_id)

        return {"success": True}

    except Exception as e:
        logger.exception("Error al ejecutar check-in para reserva %s", reserva_id)
        conn.rollback()
        conn.close()
        return {"success": False, "message": str(e)}


# -------------------------------------------
# CHECK-OUT (CONECTADO A LA BASE DE DATOS)
# -------------------------------------------
@app.get("/recepcionista/checkout")
def recepcionista_checkout():

    if session.get("tipo") != "recepcionista":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    # 🔵 1. RESERVAS ACTIVAS (SALIDAS PENDIENTES)
    cursor.execute("""
        SELECT 
            U.nombre AS nombre_huesped,
            H.numero AS numero_habitacion,
            H.precio AS precio_habitacion,
            R.fecha_entrada,
            R.fecha_salida,
            R.id AS reserva_id
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        WHERE R.estado = 'activa'
        ORDER BY R.fecha_salida ASC
    """)
    salidas = cursor.fetchall()

    # Si no hay salidas pendientes
    if not salidas:
        conn.close()
        return render_template(
            "recepcionista/checkout.html",
            nombre=session["nombre"],
            salidas=[],
            detalle=None
        )

    # 🔵 2. Primer huésped seleccionado por defecto
    huesped = salidas[0]

    # Datos del primer huésped
    (nombre_huesped, habitacion, precio, fecha_in, fecha_out, reserva_id) = huesped

    # 🔵 3. CALCULAR DIAS DE ESTANCIA
    cursor.execute("""
        SELECT DATEDIFF(DAY, fecha_entrada, fecha_salida)
        FROM Reservas
        WHERE id = ?
    """, (reserva_id,))
    dias = cursor.fetchone()[0]

    # Total habitación = precio * días
    total_habitacion = precio * dias

    conn.close()

    return render_template(
        "recepcionista/checkout.html",
        nombre=session["nombre"],
        salidas=salidas,
        detalle={
            "nombre": nombre_huesped,
            "habitacion": habitacion,
            "precio": precio,
            "fecha_in": fecha_in,
            "fecha_out": fecha_out,
            "dias": dias,
            "total_habitacion": total_habitacion
        }
    )

# ---------------- USUARIO ---------------- #
@app.get("/usuario/reservar")
def usuario_reservar():
    if session.get("tipo") != "usuario":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("SELECT id, numero FROM Habitaciones WHERE estado='disponible'")
    habitaciones = cursor.fetchall()

    conn.close()

    return render_template("usuario/inicio.html",
                           nombre=session["nombre"],
                           habitaciones=habitaciones)


@app.post("/usuario/reservar/guardar")
def usuario_guardar_reserva():
    if session.get("tipo") != "usuario":
        return redirect("/")

    habitacion_id = request.form["habitacion_id"]
    fecha_entrada = request.form["fecha_entrada"]
    fecha_salida = request.form["fecha_salida"]
    usuario_id = session["id"]

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO Reservas (usuario_id, habitacion_id, fecha_entrada, fecha_salida, estado)
        VALUES (?,?,?,?, 'activa')
    """, (usuario_id, habitacion_id, fecha_entrada, fecha_salida))
    conn.commit()

    cursor.execute("UPDATE Habitaciones SET estado='ocupada' WHERE id=?", (habitacion_id,))
    conn.commit()

    conn.close()
    return redirect("/usuario/mis-reservas")





from flask import Flask, render_template, request, redirect, url_for
import pyodbc




#---------------eleccion.html------------------#
@app.get("/habitaciones")
def listar_habitaciones():
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        id, 
        nombre, 
        descripcion, 
        estrellas, 
        precio, 
        imagen
    FROM Habitaciones
""")

    habitaciones = []
    for row in cursor.fetchall():
        habitaciones.append({
        "Id": row[0],
        "Nombre": row[1],
        "Descripcion": row[2],
        "Estrellas": row[3],
        "Precio": row[4],
        "Imagen": obtener_ruta_imagen(row[5])
    })

    
    conn.close()

    return render_template("usuario/eleccion.html", habitaciones=habitaciones)

#--------------detalle-------------------#

@app.get("/usuario/detalle/<int:id_habitacion>")
def usuario_detalle(id_habitacion):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, numero, tipo, precio, estado, descripcion, imagen, estrellas, nombre
        FROM Habitaciones
        WHERE id = ?
    """, (id_habitacion,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Habitación no encontrada", 404

    habitacion = {
        "id": row[0],
        "numero": row[1],
        "tipo": row[2],
        "precio": row[3],
        "estado": row[4],
        "descripcion": row[5],
        "imagen": obtener_ruta_imagen(row[6]),
        "estrellas": row[7],
        "nombre": row[8],
    }

    return render_template("usuario/detalle.html", habitacion=habitacion)

@app.post("/reservar/<int:id>")
def reservar(id):
    usuario_id = session.get("id")
    if not usuario_id:
        return redirect("/")

    fecha_entrada = request.form["fecha_entrada"]
    fecha_salida = request.form["fecha_salida"]

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        # Insertar la reserva
        cursor.execute("""
            INSERT INTO Reservas (usuario_id, habitacion_id, fecha_entrada, fecha_salida, estado)
            VALUES (?, ?, ?, ?, 'activa')
        """, (usuario_id, id, fecha_entrada, fecha_salida))
        conn.commit()

        # Conseguir el ID generado
        cursor.execute("SELECT @@IDENTITY")
        reserva_id = cursor.fetchone()[0]

        # Actualizar habitación a ocupada
        cursor.execute("UPDATE Habitaciones SET estado='ocupada' WHERE id=?", (id,))
        conn.commit()

        conn.close()

        # Ir a la página de pago
        return redirect(url_for("pago", reserva_id=reserva_id))

    except Exception as e:
        print("❌ Error:", e)
        return "Ocurrió un error al reservar."
@app.get("/pago/<int:reserva_id>")
def pago(reserva_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT R.id, H.nombre, H.precio, R.fecha_entrada, R.fecha_salida
        FROM Reservas R
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        WHERE R.id = ?
    """, (reserva_id,))

    reserva = cursor.fetchone()
    conn.close()

    if not reserva:
        return "Reserva no encontrada", 404

    data = {
        "id": reserva[0],
        "habitacion": reserva[1],
        "precio": reserva[2],
        "entrada": reserva[3],
        "salida": reserva[4],
    }

    return render_template("usuario/pago.html", reserva=data)
#-----------------Pagos---------------------#
# ---------------------------
# 1️⃣ CONEXIÓN A SQL SERVER
# ---------------------------
def db_connection():
    # Pagos debe usar la misma instancia de SQL Server que las reservas.
    return obtener_conexion()


def crear_tabla_pagos_si_no_existe(cursor):
    """Crea el historial de pagos la primera vez que se procesa un pago."""
    cursor.execute("""
        IF OBJECT_ID(N'dbo.Pagos', N'U') IS NULL
        BEGIN
            CREATE TABLE dbo.Pagos (
                id INT IDENTITY(1, 1) PRIMARY KEY,
                reserva_id INT NOT NULL,
                monto DECIMAL(10, 2) NOT NULL,
                metodo NVARCHAR(100) NOT NULL,
                fecha_pago DATETIME NOT NULL DEFAULT GETDATE()
            )
        END
    """)
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from flask import Flask, render_template, request, redirect, url_for, send_file


# ---------------------------
# 2️⃣ FUNCIÓN PARA PDF
# ---------------------------
def generar_pdf(nombre, monto, metodo, reserva_id):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

    if not os.path.exists("pdf"):
        os.makedirs("pdf")

    archivo_pdf = f"pdf/recibo_pago_{reserva_id}.pdf"

    doc = SimpleDocTemplate(archivo_pdf, pagesize=letter)
    elementos = []

    styles = getSampleStyleSheet()
    titulo = styles["Title"]
    normal = styles["BodyText"]

    # ---------------------------
    # 1️⃣ LOGO
    # ---------------------------
    logo_path = "static/img/nayarane.jpeg"  # Asegúrate de tenerlo en la carpeta del proyecto
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=120, height=120)
        logo.hAlign = "CENTER"
        elementos.append(logo)

    elementos.append(Spacer(1, 20))

    # ---------------------------
    # 2️⃣ TÍTULO
    # ---------------------------
    elementos.append(Paragraph("RECIBO OFICIAL DE PAGO", titulo))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("<b>Hotel Nayara</b>", normal))
    elementos.append(Paragraph("Gracias por su preferencia", normal))
    elementos.append(Spacer(1, 20))

    # ---------------------------
    # 3️⃣ TABLA DE INFORMACIÓN
    # ---------------------------
    datos = [
        ["Cliente:", nombre],
        ["Reserva ID:", reserva_id],
        ["Método de Pago:", metodo],
        ["Monto Pagado:", f"${monto}"],
        ["Fecha:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    ]

    tabla = Table(datos, colWidths=[150, 300])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 30))

    # ---------------------------
    # 4️⃣ LÍNEA DE FIRMA
    # ---------------------------
    elementos.append(Spacer(1, 40))
    elementos.append(Paragraph("______________________________", normal))
    elementos.append(Paragraph("Firma del Recepcionista", normal))
    elementos.append(Spacer(1, 20))

    # ---------------------------
    # 5️⃣ FOOTER
    # ---------------------------
    elementos.append(Paragraph(
        "<i>Este documento es un comprobante oficial de pago emitido por Hotel Nayara.</i>",
        normal
    ))
    elementos.append(Paragraph(
        "<i>Gracias por hospedarse con nosotros. ¡Esperamos verle pronto!</i>",
        normal
    ))

    doc.build(elementos)
    return archivo_pdf


# ---------------------------
# 3️⃣ RUTA FORMULARIO
# ---------------------------
@app.route("/pago")
def pago_form():
    return render_template("usuarios/pago.html")

# ---------------------------
# 4️⃣ RUTA QUE GUARDA Y GENERA PDF
# ---------------------------
@app.route("/procesar_pago", methods=["POST"])
def procesar_pago():
    nombre = request.form["nombre"]
    reserva_id = request.form["reserva"]
    monto = request.form["monto"]
    metodo = request.form["metodo"]

    # CONEXIÓN
    conn = db_connection()
    if conn is None:
        logger.error("No se pudo conectar a SQL Server al procesar un pago.")
        return render_template(
            "usuario/pago.html",
            reserva={"id": reserva_id, "precio": monto},
            error="No fue posible conectar con la base de datos. Verifica que SQL Server esté iniciado e inténtalo de nuevo."
        ), 503

    try:
        cursor = conn.cursor()
        crear_tabla_pagos_si_no_existe(cursor)

        # ✅ VALIDAR SI EXISTE EL ID DE RESERVA
        cursor.execute("SELECT 1 FROM Reservas WHERE id = ?", (reserva_id,))
        reserva = cursor.fetchone()

        if not reserva:
            return render_template(
                "usuario/pago.html",
                reserva={"id": reserva_id, "precio": monto},
                error="La reserva no existe o no está disponible."
            ), 404

        # INSERTAR PAGO
        cursor.execute("""
            INSERT INTO Pagos (reserva_id, monto, metodo)
            VALUES (?, ?, ?)
        """, (reserva_id, monto, metodo))
        conn.commit()

    except pyodbc.Error:
        logger.exception("Error de base de datos al registrar el pago de la reserva %s", reserva_id)
        return render_template(
            "usuario/pago.html",
            reserva={"id": reserva_id, "precio": monto},
            error="No se pudo registrar el pago. Inténtalo nuevamente o contacta a recepción."
        ), 500
    finally:
        conn.close()

    # GENERAR PDF
    try:
        ruta_pdf = generar_pdf(nombre, monto, metodo, reserva_id)
        return send_file(ruta_pdf, as_attachment=True)
    except Exception:
        logger.exception("El pago de la reserva %s se registró, pero no se pudo generar el PDF", reserva_id)
        return render_template(
            "usuario/pago.html",
            reserva={"id": reserva_id, "precio": monto},
            error="El pago se registró, pero no fue posible generar el comprobante PDF."
        ), 500




#--------------------QR---------------------#
# === IMPORTS NECESARIOS (añádelos al principio del archivo app.py) ===
import os
import qrcode
from PIL import Image as PILImage
from flask import send_file, url_for

# === ASEGÚRATE de que esto está UNA sola vez en todo el archivo ===
QR_DIR = os.path.join("static", "qr")
os.makedirs(QR_DIR, exist_ok=True)


# === RUTA ROBUSTA PARA GENERAR QR (acepta texto - no sólo int) ===
@app.get("/generar_qr/<habitacion>")
def generar_qr(habitacion):
    """
    Genera un QR con el texto 'Habitación <habitacion>' y pega el logo (si existe).
    Guarda el PNG en static/qr/qr_<habitacion>.png y lo devuelve.
    """
    try:
        # Texto que irá dentro del QR (puedes personalizarlo)
        texto_qr = f"Habitación {habitacion}"

        # Crear objeto QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(texto_qr)
        qr.make(fit=True)

        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        # Intentar pegar logo en el centro (si existe)
        logo_path = os.path.join("static", "img", "nayarane.jpg")  # ajusta extensión si es .jpeg/.png
        if os.path.exists(logo_path):
            logo = PILImage.open(logo_path)
            qr_w, qr_h = img_qr.size
            logo_size = int(min(qr_w, qr_h) * 0.20)   # logo ~20% del QR
            logo.thumbnail((logo_size, logo_size), PILImage.LANCZOS)

            lx = (qr_w - logo.size[0]) // 2
            ly = (qr_h - logo.size[1]) // 2

            # si el logo tiene transparencia usar como máscara
            if logo.mode in ("RGBA", "LA") or (hasattr(logo, "getchannel") and "A" in logo.getbands()):
                img_qr.paste(logo, (lx, ly), logo)
            else:
                img_qr.paste(logo, (lx, ly))

        # Guardar en static/qr con nombre seguro (remueve espacios y slashes)
        safe_name = "".join(c for c in str(habitacion) if c.isalnum() or c in ("-", "_"))
        salida = os.path.join(QR_DIR, f"qr_{safe_name}.png")
        img_qr.save(salida)

        return send_file(salida, mimetype="image/png")

    except Exception as e:
        # Devuelve un 500 simple con el error para depurar (puedes cambiar por flash)
        return f"Error generando QR: {e}", 500
    
#----------------Reportes--------------------#

@app.get("/usuario/reportes")
def reportes():
    # Solo usuarios pueden entrar
    if session.get("tipo") != "usuario":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, numero, nombre, tipo, precio, estado, descripcion, estrellas, imagen
        FROM Habitaciones
    """)
    habitaciones_raw = cursor.fetchall()
    conn.close()

    habitaciones = [
        {
            "id": h[0],
            "numero": h[1],
            "nombre": h[2],
            "tipo": h[3],
            "precio": h[4],
            "estado": h[5],
            "descripcion": h[6],
            "estrellas": int(h[7] or 0),
            "imagen": h[8],
        }
        for h in habitaciones_raw
    ]

    return render_template("usuario/reportes_habitaciones.html", habitaciones=habitaciones)

from flask import jsonify

@app.route("/enviar_reporte", methods=["POST"])
def enviar_reporte():
    data = request.json

    room_number = data.get("roomNumber")
    incident_type = data.get("incidentType")
    description = data.get("description")

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reportes (room_number, incident_type, description)
            VALUES (?, ?, ?)
        """, (room_number, incident_type, description))

        conn.commit()
        conn.close()

        return jsonify({"message": "Reporte enviado correctamente"})

    except Exception as e:
        print("❌ Error enviando reporte:", e)
        return jsonify({"message": "Error al enviar reporte"}), 500

@app.route("/recepcionista/reportes/listado")
def ver_reportes():
    if session.get("tipo") != "recepcionista":
        return redirect("/")

    conn = obtener_conexion()
    cursor = conn.cursor()

    # ======================
    # 🔥 CONSULTAR REPORTES
    # ======================
    cursor.execute("""
        SELECT id, room_number, incident_type, description, created_at
        FROM reportes
        ORDER BY created_at DESC
    """)
    reportes = cursor.fetchall()

    # ======================
    # 🔥 CONSULTAR ESTADÍSTICAS (para los cards del dashboard)
    # ======================

    cursor.execute("SELECT COUNT(*) FROM Reservas")
    total_reservas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Reservas WHERE estado='activa'")
    reservas_activas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Habitaciones WHERE estado='ocupada'")
    ocupadas = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM Habitaciones
        WHERE estado='disponible' OR estado='Disponible'
    """)
    disponibles = cursor.fetchone()[0]

    cursor.execute("""
        SELECT SUM(H.precio)
        FROM Reservas R
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
    """)
    ingresos = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT TOP 10 
            R.id, 
            U.nombre, 
            H.numero, 
            R.fecha_entrada, 
            R.fecha_salida, 
            R.estado
        FROM Reservas R
        INNER JOIN Usuarios U ON R.usuario_id = U.id
        INNER JOIN Habitaciones H ON R.habitacion_id = H.id
        ORDER BY R.id DESC
    """)
    ultimas_reservas = cursor.fetchall()

    conn.close()

    # ======================
    # 🔥 ENVIAMOS TODO AL TEMPLATE
    # ======================
    return render_template(
        "recepcionista/reportes.html",
        reportes=reportes,
        total_reservas=total_reservas,
        reservas_activas=reservas_activas,
        ocupadas=ocupadas,
        disponibles=disponibles,
        ingresos=ingresos,
        ultimas_reservas=ultimas_reservas
    )
#----------------Reportes admin--------------#
@app.route('/admin/reportes')
def admin_reportes():
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT 
            r.id,
            r.room_number,
            r.incident_type,
            r.description,
            r.created_at
        FROM reportes r
        ORDER BY r.created_at DESC
    """)

    reportes = []
    for row in cursor.fetchall():
        reportes.append({
            "id": row[0],
            "habitacion": row[1],
            "incidencia": row[2],
            "descripcion": row[3],
            "fecha": row[4]
        })

    conexion.close()
    return render_template("reportes_admin.html", reportes=reportes)

#-----------------formulario de usuarios----------#




# ---------------- EJECUTAR ---------------- #
if __name__ == "__main__":
    app.run(debug=True)
