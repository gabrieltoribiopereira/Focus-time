import time
import json
import math
import os
import select
import shutil
from datetime import datetime, timedelta
import sys
import tty
import termios

# --- deteccion de inactividad (opcional, necesita pynput) ---
try:
    import inactividad
    ERROR_IDLE = ""
except Exception as e:  # ImportError, errores de Xlib, etc.
    inactividad = None
    ERROR_IDLE = f"{type(e).__name__}: {e}"

CSI = "\x1b["
ALT_ON = f"{CSI}?1049h"
ALT_OFF = f"{CSI}?1049l"

# el config vive junto al script, no depende de desde donde lo ejecutes
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
IDLE_SEGUNDOS = 60  # segundos sin actividad para pausar (0 = desactivado)
MIN_SEGUNDOS = 60   # sesiones canceladas por debajo de esto no se guardan
DIAS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

if not sys.stdin.isatty():
    sys.exit("This program needs an interactive terminal.")

fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)

focus_time = """
███████╗ ██████╗  ██████╗██╗   ██╗███████╗    ████████╗██╗███╗   ███╗███████╗
██╔════╝██╔═══██╗██╔════╝██║   ██║██╔════╝    ╚══██╔══╝██║████╗ ████║██╔════╝
█████╗  ██║   ██║██║     ██║   ██║███████╗       ██║   ██║██╔████╔██║█████╗
██╔══╝  ██║   ██║██║     ██║   ██║╚════██║       ██║   ██║██║╚██╔╝██║██╔══╝
██║     ╚██████╔╝╚██████╗╚██████╔╝███████║       ██║   ██║██║ ╚═╝ ██║███████╗
╚═╝      ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝       ╚═╝   ╚═╝╚═╝     ╚═╝╚══════╝
"""


def leer_tecla():
    """Lee UNA tecla y devuelve su nombre. No guarda estado."""
    a = os.read(fd, 1)
    if a == b"":
        return "quit"
    if a == b"\x1b":
        # esc suelto: si no llega nada mas, es escape (sin bloquear)
        if select.select([fd], [], [], 0.05)[0]:
            c = os.read(fd, 2)  # solo 2 bytes: asi no te comes flechas pulsadas rapido
            if c in (b"[C", b"OC"):
                return "right"
            elif c in (b"[D", b"OD"):
                return "left"
            elif c in (b"[A", b"OA"):
                return "up"
            elif c in (b"[B", b"OB"):
                return "down"
        return "escape"
    elif a in (b"\r", b"\n"):
        return "enter"
    elif a in (b"q", b"\x03"):
        return "quit"
    return a.decode(errors="ignore")


def dibujar_menu(opciones, indice):
    """Solo dibuja. No decide nada."""
    trozos = []
    for i, opcion in enumerate(opciones):
        if i == indice:
            trozos.append(f"{CSI}7m {opcion} {CSI}0m")
        else:
            trozos.append(f" {opcion} ")
    print(f"\r{CSI}K" + "  ".join(trozos), end="", flush=True)


def menu(opciones):
    """Devuelve la opción elegida, o None si se cancela."""
    indice = 0
    try:
        tty.setcbreak(fd)
        sys.stdout.write(f"{CSI}?25l")
        while True:
            dibujar_menu(opciones, indice)
            tecla = leer_tecla()

            if tecla == "left":
                indice = (indice - 1) % len(opciones)
            elif tecla == "right":
                indice = (indice + 1) % len(opciones)
            elif tecla == "enter":
                return opciones[indice]
            elif tecla == "quit":
                return None
    finally:
        sys.stdout.write(f"{CSI}?25h")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print()


def pedir_texto(texto):
    """Pide un texto. Devuelve '' si no se escribe nada."""
    termios.tcflush(fd, termios.TCIFLUSH)
    try:
        return input(texto).strip()
    except EOFError:
        return ""


def pedir_entero(texto, minimo=0, maximo=None, cancelable=True):
    """Pide un entero validado. Devuelve None si se deja vacio (y es cancelable)."""
    while True:
        valor = pedir_texto(texto)
        if valor == "":
            if cancelable:
                return None
            continue
        try:
            n = int(valor)
        except ValueError:
            print("Enter a whole number.")
            continue
        if n < minimo or (maximo is not None and n > maximo):
            print("Value out of range.")
            continue
        return n


def esperar_tecla():
    """Espera UNA tecla (sin eco) y vuelve al modo normal."""
    tty.setcbreak(fd)
    try:
        termios.tcflush(fd, termios.TCIFLUSH)
        leer_tecla()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def guardar(datos):
    """Guarda sin riesgo de dejar el json a medias."""
    with open(CONFIG + ".tmp", "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    os.replace(CONFIG + ".tmp", CONFIG)


def clave_semana(dt):
    """Semana ISO (lunes-domingo), p. ej. '2026-W44'."""
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def sesiones_validas(datos):
    """Devuelve [(fin, duracion_s, sesion)] ignorando entradas rotas."""
    out = []
    for s in datos.get("sesiones", []):
        try:
            out.append((datetime.fromisoformat(s["fin"]), int(s["duracion_segundos"]), s))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def segundos_semana(datos, clave):
    """Segundos hechos en la semana `clave` (el resto de semanas no cuentan)."""
    return sum(d for fin, d, _ in sesiones_validas(datos) if clave_semana(fin) == clave)


def fmt(seg):
    """Segundos -> '2h 05m'."""
    h, resto = divmod(int(seg), 3600)
    m = resto // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def hacer_barra(porcentaje, ancho):
    """Barra de progreso. Se queda en el 100% aunque te pases."""
    llenos = int(ancho * (min(max(porcentaje, 0), 100) / 100))
    return "█" * llenos + "░" * (ancho - llenos)


def ancho_terminal():
    return shutil.get_terminal_size((80, 24)).columns


def temporizador(total):
    """Cuenta atrás que solo avanza con actividad.

    Devuelve (segundos_activos, completa, inicio, segundos_inactivo).
    """
    usar_idle = IDLE_SEGUNDOS > 0 and inactividad is not None
    ancho = max(10, min(67, ancho_terminal() - 30))

    print("Press q to stop and keep your progress.")
    if IDLE_SEGUNDOS > 0 and inactividad is None:
        print(f"Idle detection off ({ERROR_IDLE}).")
    elif usar_idle:
        print(f"Auto-pause after {IDLE_SEGUNDOS}s without keyboard/mouse activity.")
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
            print("Wayland detected: keys/mouse outside this terminal may not be seen.")
    print()

    cancelado = False
    pausado = False
    ultimo = None
    activo = 0.0  # segundos de trabajo efectivo
    inicio = datetime.now()
    t0 = tick = time.monotonic()
    if usar_idle:
        inactividad.marcar_actividad()  # empieza el contador desde cero

    sys.stdout.write(f"{CSI}?25l")
    try:
        tty.setcbreak(fd)  # evita que lo que teclees ensucie la barra
        while True:
            ahora = time.monotonic()
            dt = ahora - tick
            tick = ahora

            # --- pausa por inactividad ---
            if usar_idle and inactividad.segundos_inactivo() >= IDLE_SEGUNDOS:
                if not pausado:
                    pausado = True
                    # los segundos previos al umbral ya estaban sumados: se descuentan una vez
                    inact = inactividad.segundos_inactivo()
                    activo = max(0.0, activo - max(0.0, inact - dt))
            else:
                pausado = False
                activo += dt

            # --- dibujar (solo si cambia algo) ---
            restante = max(0, math.ceil(total - activo))
            estado = (restante, pausado)
            if estado != ultimo:
                ultimo = estado
                porcentaje = min(100.0, activo / total * 100)
                hh = restante // 3600
                mm = (restante % 3600) // 60
                ss = restante % 60
                reloj = f"{hh:02d}:{mm:02d}:{ss:02d}"
                nota = f"  {CSI}93mPAUSED (idle){CSI}0m" if pausado else ""
                print(f"\r{CSI}K{reloj: <10}{hacer_barra(porcentaje, ancho)} {round(porcentaje, 0)}%{nota}",
                      end="", flush=True)

            if activo >= total:
                break

            # --- esperar tecla (0.2s max, no bloquea el reloj) ---
            if select.select([fd], [], [], 0.2)[0]:
                if leer_tecla() == "quit":
                    cancelado = True
                    break
                if usar_idle:  # una tecla en esta terminal tambien es actividad
                    inactividad.marcar_actividad()
    except KeyboardInterrupt:
        cancelado = True
    finally:
        sys.stdout.write(f"{CSI}?25h")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    pared = time.monotonic() - t0
    segundos = min(total, int(activo)) if cancelado else total
    return segundos, not cancelado, inicio, max(0, int(pared - activo))


def historial(datos):
    """Pantalla de registro: semana actual, semanas anteriores y ultimas sesiones."""
    ses = sesiones_validas(datos)
    ses.sort(key=lambda x: x[0], reverse=True)
    actual = clave_semana(datetime.now())

    sys.stdout.write(f"{CSI}2J{CSI}H")
    print(f"{CSI}94mHISTORY{CSI}0m\n")

    # --- semana actual, dia a dia ---
    hoy = datetime.now().date()
    lunes = hoy - timedelta(days=hoy.weekday())
    por_dia = {}
    for fin, dur, _ in ses:
        por_dia[fin.date()] = por_dia.get(fin.date(), 0) + dur
    max_dia = max([por_dia.get(lunes + timedelta(days=i), 0) for i in range(7)] + [1])

    print(f"This week ({actual}): {fmt(segundos_semana(datos, actual))} / {datos['weekly goal']}h")
    for i in range(7):
        d = lunes + timedelta(days=i)
        seg = por_dia.get(d, 0)
        marca = "  <" if d == hoy else ""
        print(f"  {DIAS[i]} {d:%d/%m}  {fmt(seg):>8}  {'█' * int(20 * seg / max_dia)}{marca}")

    # --- semanas anteriores ---
    semanas = {}
    for fin, dur, _ in ses:
        k = clave_semana(fin)
        semanas[k] = semanas.get(k, 0) + dur
    pasadas = sorted((k for k in semanas if k != actual), reverse=True)[:8]
    if pasadas:
        print("\nPrevious weeks:")
        for k in pasadas:
            obj = datos["historial_objetivos"].get(k, datos["weekly goal"])
            ok = semanas[k] >= obj * 3600
            print(f"  {k}  {fmt(semanas[k]):>8} / {obj}h  {'✓' if ok else '✗'}")

    # --- ultimas sesiones ---
    print("\nLast sessions:")
    if not ses:
        print("  (none yet)")
    for fin, dur, s in ses[:10]:
        extra = "" if s.get("completa", True) else "  (stopped early)"
        if s.get("inactivo_segundos", 0) >= 60:
            extra += f"  (idle {fmt(s['inactivo_segundos'])})"
        print(f"  {fin:%d/%m %H:%M}  {fmt(dur):>8}  {s.get('etiqueta') or ''}{extra}")

    print(f"\n{CSI}92mPress any key...{CSI}0m", end="", flush=True)
    esperar_tecla()


try:
    sys.stdout.write(ALT_ON)
    sys.stdout.flush()

    # --- cargar o crear el config (solo una vez) ---
    datos = None
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                datos = json.load(f)
            if int(datos["weekly goal"]) < 1:
                raise ValueError("objetivo invalido")
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError):
            os.replace(CONFIG, CONFIG + ".bak")  # no pierdas el archivo roto
            datos = None

    if datos is None:
        sys.stdout.write(f"{CSI}2J{CSI}H")
        print(f"{CSI}94m{focus_time}{CSI}0m")
        objetivo_semanal = pedir_entero("Weekly goal (in hours): ", 1, 168, cancelable=False)
        datos = {"weekly goal": objetivo_semanal, "sesiones": []}

    datos.setdefault("sesiones", [])
    datos.setdefault("historial_objetivos", {})
    guardar(datos)

    # ===== BUCLE PRINCIPAL: vuelve al menu tras cada accion =====
    while True:
        sys.stdout.write(f"{CSI}2J{CSI}H")
        print(f"{CSI}94m{focus_time}{CSI}0m")

        # --- semana actual (el progreso se reinicia solo cada semana) ---
        clave = clave_semana(datetime.now())
        if clave not in datos["historial_objetivos"]:
            datos["historial_objetivos"][clave] = datos["weekly goal"]
            guardar(datos)

        # --- barra del progreso semanal ---
        objetivo_segundos = datos["weekly goal"] * 3600
        hechos = segundos_semana(datos, clave)
        porcentajeSemanal = hechos / objetivo_segundos * 100

        ancho = max(10, min(77, ancho_terminal() - 10))
        barra = hacer_barra(porcentajeSemanal, ancho)
        print(f"Week {clave}: {fmt(hechos)} / {datos['weekly goal']}h")
        print(f"{barra} {round(porcentajeSemanal, 1)}%\n")

        elegido = menu(["Start timer", "Goal", "History", "Quit"])

        if elegido is None or elegido == "Quit":
            break

        elif elegido == "Start timer":
            h = pedir_entero("Hours (empty = cancel): ", 0, 24)
            if h is None:
                continue
            m = pedir_entero("Minutes (0-59): ", 0, 59)
            if m is None:
                continue
            total = h * 3600 + m * 60

            if total > 0:
                etiqueta = pedir_texto("What are you working on? (optional): ")
                segundos, completa, inicio, inactivo = temporizador(total)

                # --- guardar la sesion ---
                if completa or segundos >= MIN_SEGUNDOS:
                    datos["sesiones"].append({
                        "inicio": inicio.isoformat(timespec="seconds"),
                        "fin": datetime.now().isoformat(timespec="seconds"),
                        "duracion_segundos": segundos,  # solo tiempo activo
                        "inactivo_segundos": inactivo,  # tiempo en pausa por inactividad
                        "etiqueta": etiqueta,
                        "completa": completa,
                    })
                    guardar(datos)

                if completa:
                    sys.stdout.write("\a")  # campanita
                    mensaje = "Session complete! Press any key..."
                elif segundos >= MIN_SEGUNDOS:
                    mensaje = f"Stopped early, saved {fmt(segundos)}. Press any key..."
                else:
                    mensaje = f"Stopped after {segundos}s of activity: too short, not saved. Press any key..."

                print(f"\n\n{CSI}92m{mensaje}{CSI}0m", end="", flush=True)
                esperar_tecla()

            else:
                print("Duration must be greater than 0. Press any key...", end="", flush=True)
                esperar_tecla()

        elif elegido == "Goal":
            print(f"Current weekly goal: {datos['weekly goal']}h")
            nuevo = pedir_entero("New weekly goal in hours (empty = cancel): ", 1, 168)
            if nuevo is not None:
                datos["weekly goal"] = nuevo
                datos["historial_objetivos"][clave] = nuevo
                guardar(datos)

        elif elegido == "History":
            historial(datos)

except KeyboardInterrupt:
    pass

finally:
    sys.stdout.write(f"{CSI}?25h{ALT_OFF}")
    sys.stdout.flush()
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
