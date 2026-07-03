from flask import session, redirect


def requiere_login():
    """Devuelve una redirección a /login si no hay sesión activa, None si hay sesión."""
    if "usuario" not in session:
        return redirect("/login")
    return None


def requiere_staff():
    """Bloquea el rol 'cliente' — solo roles de staff acceden a rutas operativas."""
    if "usuario" not in session:
        return redirect("/login")
    if session.get("rol") == "cliente":
        return redirect("/tienda/")
    return None


def requiere_rol(*roles):
    """Devuelve una redirección si el rol del usuario no está en la lista permitida."""
    if "usuario" not in session:
        return redirect("/login")
    if session.get("rol") not in roles:
        return redirect("/login")
    return None
