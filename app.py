import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

from extensions import bcrypt
from database import conectar
from db_config import USE_POSTGRES

from blueprints.dashboard import dashboard_bp
from blueprints.gasolineras import gasolineras_bp
from blueprints.clientes import clientes_bp
from blueprints.vehiculos import vehiculos_bp
from blueprints.choferes import choferes_bp
from blueprints.modulos import modulos_bp
from blueprints.depositos import depositos_bp
from blueprints.recepciones import recepciones_bp
from blueprints.transferencias import transferencias_bp
from blueprints.unidades import unidades_bp
from blueprints.tarjetas import tarjetas_bp
from blueprints.habilitaciones import habilitaciones_bp
from blueprints.despachos import despachos_bp
from blueprints.conciliacion import conciliacion_bp
from blueprints.tl38 import tl38_bp
from blueprints.reportes import reportes_bp
from blueprints.portal import portal_bp
from blueprints.usuarios import usuarios_bp
from blueprints.configuracion import configuracion_bp
from blueprints.turno import turno_bp
from blueprints.puertos import puertos_bp


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY no configurada — define la variable de entorno SECRET_KEY")
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = USE_POSTGRES  # True en Render (HTTPS), False en dev local
app.config["WTF_CSRF_ENABLED"] = True

bcrypt.init_app(app)

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.after_request
def set_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, nombre, password_hash, rol, activo
            FROM usuarios
            WHERE email = ?
        """, (email,))
        fila = cur.fetchone()

        if fila and fila["activo"] and bcrypt.check_password_hash(fila["password_hash"], password):
            session.permanent = True
            session["usuario"] = email
            session["nombre"] = fila["nombre"]
            session["rol"] = fila["rol"]
            session["user_id"] = fila["id"]

            # Para usuarios cliente: cargar cliente_id
            if fila["rol"] == "cliente":
                cur.execute("""
                    SELECT cliente_id FROM cliente_usuarios WHERE usuario_id = ?
                """, (fila["id"],))
                cu = cur.fetchone()
                session["cliente_id"] = cu["cliente_id"] if cu else None

            conn.close()

            if fila["rol"] == "cliente":
                return redirect("/portal/")
            return redirect("/dashboard")

        conn.close()
        return render_template("login.html", error="Credenciales incorrectas")

    return render_template("login.html")


@app.route("/")
def root():
    if "usuario" in session:
        if session.get("rol") == "cliente":
            return redirect("/portal/")
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


app.register_blueprint(dashboard_bp)
app.register_blueprint(gasolineras_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(vehiculos_bp)
app.register_blueprint(choferes_bp)
app.register_blueprint(modulos_bp)
app.register_blueprint(depositos_bp)
app.register_blueprint(recepciones_bp)
app.register_blueprint(transferencias_bp)
app.register_blueprint(unidades_bp)
app.register_blueprint(tarjetas_bp)
app.register_blueprint(habilitaciones_bp)
app.register_blueprint(despachos_bp)
app.register_blueprint(conciliacion_bp)
app.register_blueprint(tl38_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(portal_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(configuracion_bp)
app.register_blueprint(turno_bp)
app.register_blueprint(puertos_bp)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
for _sub in ["tickets", "vehiculos", "odometros"]:
    os.makedirs(os.path.join(UPLOAD_FOLDER, _sub), exist_ok=True)

# Inicializar base de datos y migraciones
if USE_POSTGRES:
    from migraciones_pg import ejecutar_migraciones_pg
    ejecutar_migraciones_pg(bcrypt)
else:
    from migraciones import ejecutar_migraciones
    ejecutar_migraciones(bcrypt)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=True)
