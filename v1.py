import time
import json
import os
from datetime import datetime
import sys
import tty
import termios

CSI = "\x1b["
ALT_ON = f"{CSI}?1049h"
ALT_OFF = f"{CSI}?1049l"

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
    a = sys.stdin.read(1)
    if a == "\x1b":
        c = sys.stdin.read(2)
        if c[1] == "C":
            return "right"
        elif c[1] == "D":
            return "left"
        elif c[1] == "A":
            return "up"
        elif c[1] == "B":
            return "down"
        return "escape"
    elif a in ("\r", "\n"):
        return "enter"
    elif a in ("q", "\x03"):
        return "quit"
    return a


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


try:
    sys.stdout.write(ALT_ON)
    sys.stdout.flush()

    # --- cargar o crear el config (solo una vez) ---
    if os.path.exists("config.json"):
        with open("config.json") as f:
            datos = json.load(f)
    else:
        sys.stdout.write(f"{CSI}2J{CSI}H")
        print(f"{CSI}94m{focus_time}{CSI}0m")
        ojetivo_semanal = int(input("Weekly goal(in hours):"))
        datos = {"weekly goal": ojetivo_semanal, "sesiones": []}
        with open("config.json", "w") as f:
            json.dump(datos, f, indent=2)

    # ===== BUCLE PRINCIPAL: vuelve al menu tras cada accion =====
    while True:
        sys.stdout.write(f"{CSI}2J{CSI}H")
        print(f"{CSI}94m{focus_time}{CSI}0m")

        # --- barra del progreso semanal ---
        objetivo_segundos = datos["weekly goal"] * 3600
        hechos = sum(s["duracion_segundos"] for s in datos.get("sesiones", []))
        porcentajeSemanal = hechos / objetivo_segundos * 100

        ancho = 77
        llenos = int(ancho * (min(porcentajeSemanal, 100) / 100))
        vacios = ancho - llenos
        barra = "█" * llenos + "░" * vacios
        print(f"{barra} {round(porcentajeSemanal, 1)}%\n")

        elegido = menu(["Start timer", "Goal", "Settings", "Quit"])

        if elegido is None or elegido == "Quit":
            break

        elif elegido == "Start timer":
            print(f"{CSI}1A", end="")
            print(f"{CSI}K", end="")
            h = int(input("Hours: "))
            print(f"{CSI}1A", end="")
            print(f"{CSI}K", end="")
            m = int(input("Minutes: "))
            print(f"{CSI}1A", end="")
            print(f"{CSI}K", end="")
            total = h * 3600 + m * 60

            if total > 0:
                for restante in range(total, -1, -1):
                    porcentaje = (1 - (restante / total)) * 100
                    hh = restante // 3600
                    mm = (restante % 3600) // 60
                    ss = restante % 60
                    ancho = 67
                    llenos = int(ancho * (porcentaje / 100))
                    vacios = ancho - llenos
                    barra = "█" * llenos + "░" * vacios
                    reloj = f"{hh:02d}:{mm:02d}:{ss:02d}"
                    print(f"\r{CSI}K{reloj: <10}{barra} {round(porcentaje, 0)}%", end="", flush=True)
                    if restante != 0:
                        time.sleep(1)

                # --- guardar la sesion ---
                datos.setdefault("sesiones", []).append({
                    "fin": datetime.now().isoformat(timespec="seconds"),
                    "duracion_segundos": total,
                })
                with open("config.json", "w") as f:
                    json.dump(datos, f, indent=2)

                print(f"\n\n{CSI}92mSession complete! Press any key...{CSI}0m", end="", flush=True)
                tty.setcbreak(fd)
                sys.stdin.read(1)
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

        elif elegido == "Goal":
            print(f"{CSI}1A", end="")
            print(f"{CSI}K", end="")
            datos["weekly goal"] = int(input("Weekly goal(in hours): "))
            with open("config.json", "w") as f:
                json.dump(datos, f, indent=2)

finally:
    sys.stdout.write(ALT_OFF)
    sys.stdout.flush()
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
