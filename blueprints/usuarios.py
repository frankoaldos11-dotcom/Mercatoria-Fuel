from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from extensions import bcrypt
from utils.auth import requiere_rol, requiere_login

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

_ROLES_LISTA = [
    ("admin",               "Admin"),
    ("pm",                  "PM"),
    ("operario",            "Operario"),
    ("operario_deposito",   "Operario Depósito"),
    ("operario_gasolinera", "Operario Gasolinera"),
    ("supervisor",          "Supervisor"),
    ("cliente",             "Cliente"),
]


def _solo_admin():
    redir = requiere_rol("admin")
    return redir


# ── Listado ───────────────────────────────────────────────────────────────────

@usuarios_bp.route("/")
def listado():
    redir = _solo_admin()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.nombre, u.email, u.rol, u.activo, u.created_at,
               cu.cliente_id,
               cl.nombre AS cliente_nombre
        FROM usuarios u
        LEFT JOIN cliente_usuarios cu ON cu.usuario_id = u.id
        LEFT JOIN clientes cl ON cl.id = cu.cliente_id
        ORDER BY u.created_at DESC
    """)
    lista = cur.fetchall()
    conn.close()

    return render_template("usuarios/listado.html", lista=lista)


# ── Crear ─────────────────────────────────────────────────────────────────────

@usuarios_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = _solo_admin()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, codigo FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    conn.close()

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        rol = request.form.get("rol", "operario").strip()
        activo = 1 if request.form.get("activo") else 0
        cliente_id = request.form.get("cliente_id", "").strip() or None

        if not nombre:
            error = "El nombre es obligatorio."
        elif not email:
            error = "El email es obligatorio."
        elif not password:
            error = "La contraseña es obligatoria."
        elif len(password) < 8:
            error = "La contraseña debe tener al menos 8 caracteres."
        elif password != confirm:
            error = "Las contraseñas no coinciden."
        elif rol not in [r[0] for r in _ROLES_LISTA]:
            error = "Rol inválido."
        elif rol == "cliente" and not cliente_id:
            error = "Debe seleccionar el cliente asociado para usuarios con rol cliente."
        else:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
            if cur.fetchone():
                error = "Ya existe un usuario con ese email."
                conn.close()
            else:
                hash_pw = bcrypt.generate_password_hash(password).decode("utf-8")
                cur.execute("""
                    INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
                    VALUES (?, ?, ?, ?, ?)
                """, (nombre, email, hash_pw, rol, activo))
                nuevo_id = cur.lastrowid
                if rol == "cliente" and cliente_id:
                    cur.execute("""
                        INSERT OR IGNORE INTO cliente_usuarios (cliente_id, usuario_id)
                        VALUES (?, ?)
                    """, (cliente_id, nuevo_id))
                conn.commit()
                conn.close()
                return redirect("/usuarios/?ok=1")

    return render_template(
        "usuarios/crear.html",
        error=error,
        clientes=clientes,
        roles=_ROLES_LISTA,
    )


# ── Editar ────────────────────────────────────────────────────────────────────

@usuarios_bp.route("/<int:uid>/editar", methods=["GET", "POST"])
def editar(uid):
    redir = _solo_admin()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.*, cu.cliente_id
        FROM usuarios u
        LEFT JOIN cliente_usuarios cu ON cu.usuario_id = u.id
        WHERE u.id = ?
    """, (uid,))
    usuario = cur.fetchone()

    if not usuario:
        conn.close()
        return redirect("/usuarios/")

    cur.execute("SELECT id, nombre, codigo FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    conn.close()

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        rol = request.form.get("rol", "operario").strip()
        activo = 1 if request.form.get("activo") else 0
        cliente_id = request.form.get("cliente_id", "").strip() or None

        propio = (uid == session.get("user_id"))

        if not nombre:
            error = "El nombre es obligatorio."
        elif not email:
            error = "El email es obligatorio."
        elif password and len(password) < 8:
            error = "La contraseña debe tener al menos 8 caracteres."
        elif password and password != confirm:
            error = "Las contraseñas no coinciden."
        elif rol not in [r[0] for r in _ROLES_LISTA]:
            error = "Rol inválido."
        elif propio and rol != usuario["rol"]:
            error = "No puedes cambiar tu propio rol."
        elif rol == "cliente" and not cliente_id:
            error = "Debe seleccionar el cliente asociado para usuarios con rol cliente."
        else:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM usuarios WHERE email = ? AND id != ?", (email, uid))
            if cur.fetchone():
                error = "Ya existe otro usuario con ese email."
                conn.close()
            else:
                if password:
                    hash_pw = bcrypt.generate_password_hash(password).decode("utf-8")
                    cur.execute("""
                        UPDATE usuarios SET nombre=?, email=?, password_hash=?, rol=?,
                        activo=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
                    """, (nombre, email, hash_pw, rol, activo, uid))
                else:
                    cur.execute("""
                        UPDATE usuarios SET nombre=?, email=?, rol=?,
                        activo=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
                    """, (nombre, email, rol, activo, uid))

                # Gestionar cliente_usuarios
                cur.execute("DELETE FROM cliente_usuarios WHERE usuario_id = ?", (uid,))
                if rol == "cliente" and cliente_id:
                    cur.execute("""
                        INSERT OR IGNORE INTO cliente_usuarios (cliente_id, usuario_id)
                        VALUES (?, ?)
                    """, (cliente_id, uid))

                conn.commit()
                conn.close()
                return redirect(f"/usuarios/?ok=1")

    return render_template(
        "usuarios/editar.html",
        usuario=usuario,
        error=error,
        clientes=clientes,
        roles=_ROLES_LISTA,
    )


# ── Toggle activo ─────────────────────────────────────────────────────────────

@usuarios_bp.route("/<int:uid>/toggle", methods=["POST"])
def toggle(uid):
    redir = _solo_admin()
    if redir:
        return redir

    if uid == session.get("user_id"):
        return redirect("/usuarios/?access_error=No+puedes+desactivar+tu+propia+cuenta")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT activo FROM usuarios WHERE id = ?", (uid,))
    row = cur.fetchone()
    if row:
        nuevo_estado = 0 if row["activo"] else 1
        cur.execute("UPDATE usuarios SET activo=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (nuevo_estado, uid))
        conn.commit()
    conn.close()
    return redirect("/usuarios/?ok=1")


# ── Cambiar contraseña propia ─────────────────────────────────────────────────

@usuarios_bp.route("/cambiar-password", methods=["GET", "POST"])
def cambiar_password():
    redir = requiere_login()
    if redir:
        return redir

    error = None
    ok = False

    if request.method == "POST":
        actual = request.form.get("password_actual", "")
        nueva = request.form.get("password_nueva", "")
        confirm = request.form.get("confirm_password", "")

        if not actual or not nueva or not confirm:
            error = "Todos los campos son obligatorios."
        elif len(nueva) < 8:
            error = "La nueva contraseña debe tener al menos 8 caracteres."
        elif nueva != confirm:
            error = "Las contraseñas nuevas no coinciden."
        else:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT password_hash FROM usuarios WHERE id = ?", (session["user_id"],))
            row = cur.fetchone()
            if not row or not bcrypt.check_password_hash(row["password_hash"], actual):
                error = "La contraseña actual es incorrecta."
                conn.close()
            else:
                hash_nuevo = bcrypt.generate_password_hash(nueva).decode("utf-8")
                cur.execute("""
                    UPDATE usuarios SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
                """, (hash_nuevo, session["user_id"]))
                conn.commit()
                conn.close()
                ok = True

    return render_template("usuarios/cambiar_password.html", error=error, ok=ok)
