import sys, tty, termios, select, time, json, os
from datetime import datetime

CSI = "\x1b["
ALT_ON = f"{CSI}?1049h"
ALT_OFF = f"{CSI}?1049l"
fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)

BANNER = """
███████╗ ██████╗  ██████╗██╗   ██╗███████╗    ████████╗██╗███╗   ███╗███████╗
██╔════╝██╔═══██╗██╔════╝██║   ██║██╔════╝    ╚══██╔══╝██║████╗ ████║██╔════╝
█████╗  ██║   ██║██║     ██║   ██║███████╗       ██║   ██║██╔████╔██║█████╗
██╔══╝  ██║   ██║██║     ██║   ██║╚════██║       ██║   ██║██║╚██╔╝██║██╔══╝
██║     ╚██████╔╝╚██████╗╚██████╔╝███████║       ██║   ██║██║ ╚═╝ ██║███████╗
╚═╝      ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝       ╚═╝   ╚═╝╚═╝     ╚═╝╚══════╝"""


def hay_tecla():
    return bool(select.select([sys.stdin], [], [], 0)[0])


def leer_tecla():
    a = sys.stdin.read(1)
    if a == "\x1b":
        if not hay_tecla():
            return "escape"
        c = sys.stdin.read(2)
        return {"C": "right", "D": "left", "A": "up", "B": "down"}.get(c[1], "escape")
    elif a in ("\r", "\n"):
        return "enter"
    elif a in ("q", "\x03"):
        return "quit"
    return a


def barra(porcentaje, ancho):
    porcentaje = max(0, min(100, porcentaje))
    llenos = int(ancho * porcentaje / 100)
    return "█" * llenos + "░" * (ancho - llenos)


def linea_menu(opciones, indice):
    trozos = []
    for i, opcion in enumerate(opciones):
        if i == indice:
            trozos.append(f"{CSI}7m {opcion} {CSI}0m")
        else:
            trozos.append(f" {opcion} ")
    return "  ".join(trozos)


def pedir(texto):
    """Sale de cbreak un momento para poder usar input() con eco."""
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.stdout.write(f"{CSI}?25h")
    try:
        return int(input(texto))
    except ValueError:
        return 0
    finally:
        tty.setcbreak(fd)
        sys.stdout.write(f"{CSI}?25l")


try:
    sys.stdout.write(ALT_ON + f"{CSI}2J{CSI}H")
    sys.stdout.flush()

    # --- config ---
    if os.path.exists("config.json"):
        with open("config.json") as f:
            datos = json.load(f)
    else:
        print(f"{CSI}94m{BANNER}{CSI}0m\n")
        objetivo = int(input("Weekly goal (in hours): "))
        datos = {"weekly goal": objetivo, "sesiones": []}
        with open("config.json", "w") as f:
            json.dump(datos, f, indent=2)

    objetivo_segundos = datos["weekly goal"] * 3600

    # --- estado ---
    opciones = ["Start timer", "Stats", "Settings", "Quit"]
    indice = 0
    timer_activo = False
    inicio = 0.0
    total = 0
    mensaje = ""

    tty.setcbreak(fd)
    sys.stdout.write(f"{CSI}?25l")

    while True:
        # 1. ACTUALIZAR
        if timer_activo:
            restante = total - int(time.perf_counter() - inicio)
            if restante <= 0:
                restante = 0
                timer_activo = False
                datos.setdefault("sesiones", []).append({
                    "fin": datetime.now().isoformat(timespec="seconds"),
                    "duracion_segundos": total,
                })
                with open("config.json", "w") as f:
                    json.dump(datos, f, indent=2)
                mensaje = "Session complete!"

        hechos = sum(s["duracion_segundos"] for s in datos.get("sesiones", []))
        pct_semanal = hechos / objetivo_segundos * 100

        # 2. DIBUJAR (un frame entero desde arriba)
        lineas = [f"{CSI}94m{l}{CSI}0m" for l in BANNER.split("\n")]
        lineas.append("")
        lineas.append(f"{barra(pct_semanal, 60)} {round(pct_semanal, 1)}% weekly")
        lineas.append("")
        if timer_activo or mensaje:
            if timer_activo:
                pct = (1 - restante / total) * 100
                reloj = f"{restante//3600:02d}:{restante%3600//60:02d}:{restante%60:02d}"
                lineas.append(f"{reloj:<10}{barra(pct, 50)} {round(pct)}%")
            else:
                lineas.append(f"{CSI}92m{mensaje}{CSI}0m")
        else:
            lineas.append("")
        lineas.append("")
        lineas.append(linea_menu(opciones, indice))

        frame = [f"{CSI}H"]
        for l in lineas:
            frame.append(l + f"{CSI}K\r\n")
        frame.append(f"{CSI}J")
        sys.stdout.write("".join(frame))
        sys.stdout.flush()

        # 3. TECLAS
        while hay_tecla():
            tecla = leer_tecla()
            if tecla == "left":
                indice = (indice - 1) % len(opciones)
            elif tecla == "right":
                indice = (indice + 1) % len(opciones)
            elif tecla == "quit":
                break
            elif tecla == "enter":
                elegido = opciones[indice]
                if elegido == "Quit":
                    break
                elif elegido == "Start timer" and not timer_activo:
                    sys.stdout.write(f"{CSI}H{CSI}J")
                    h = pedir("Hours: ")
                    m = pedir("Minutes: ")
                    total = h * 3600 + m * 60
                    if total > 0:
                        inicio = time.perf_counter()
                        timer_activo = True
                        mensaje = ""

        time.sleep(1 / 5)

finally:
    sys.stdout.write(f"{CSI}?25h" + ALT_OFF)
    sys.stdout.flush()
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
