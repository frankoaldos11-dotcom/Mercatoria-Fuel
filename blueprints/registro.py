import re

from utils.mailer import bienvenida
from flask import Blueprint, render_template, request, redirect
from database import conectar
from extensions import bcrypt

registro_bp = Blueprint("registro", __name__, url_prefix="/registro")

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


@registro_bp.route("/", methods=["GET", "POST"])
def index():
    error = None
    form = {}

    if request.method == "POST":
        form = request.form
        nombre = form.get("nombre", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        confirm = form.get("confirm_password", "")
        empresa = form.get("empresa", "").strip()

        if not nombre:
            error = "El nombre completo es obligatorio."
        elif not email or not _EMAIL_RE.match(email):
            error = "Ingresa un correo electrónico válido."
        elif len(password) < 8:
            error = "La contraseña debe tener al menos 8 caracteres."
        elif password != confirm:
            error = "Las contraseñas no coinciden."

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
            if cur.fetchone():
                error = "Ya existe una cuenta con ese correo electrónico."
                conn.close()
            else:
                nombre_completo = f"{nombre} — {empresa}" if empresa else nombre
                hash_pw = bcrypt.generate_password_hash(password).decode("utf-8")
                cur.execute("""
                    INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
                    VALUES (?, ?, ?, 'cliente', 0)
                """, (nombre_completo, email, hash_pw))
                nuevo_id = cur.lastrowid
                conn.commit()
                conn.close()
                bienvenida(nombre_completo, email, nuevo_id)
                return redirect("/registro/ok")

    return render_template("registro.html", error=error, form=form)


@registro_bp.route("/ok")
def ok():
    return render_template("registro_ok.html")
