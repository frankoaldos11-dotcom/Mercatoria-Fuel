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
from blueprints.modulos import modulos_bp


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("SECRET_KEY no configurada — define la variable de entorno SECRET_KEY")
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
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
        conn.close()

        if fila and fila["activo"] and bcrypt.check_password_hash(fila["password_hash"], password):
            session.permanent = True
            session["usuario"] = email
            session["nombre"] = fila["nombre"]
            session["rol"] = fila["rol"]
            session["user_id"] = fila["id"]
            return redirect("/dashboard")

        return render_template("login.html", error="Credenciales incorrectas")

    return render_template("login.html")


@app.route("/")
def root():
    if "usuario" in session:
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


app.register_blueprint(dashboard_bp)
app.register_blueprint(gasolineras_bp)
app.register_blueprint(modulos_bp)

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
