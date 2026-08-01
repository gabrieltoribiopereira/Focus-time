import time
import json
import os
from datetime import datetime

CSI = "\x1b["
focus_time = """
███████╗ ██████╗  ██████╗██╗   ██╗███████╗    ████████╗██╗███╗   ███╗███████╗
██╔════╝██╔═══██╗██╔════╝██║   ██║██╔════╝    ╚══██╔══╝██║████╗ ████║██╔════╝
█████╗  ██║   ██║██║     ██║   ██║███████╗       ██║   ██║██╔████╔██║█████╗
██╔══╝  ██║   ██║██║     ██║   ██║╚════██║       ██║   ██║██║╚██╔╝██║██╔══╝
██║     ╚██████╔╝╚██████╗╚██████╔╝███████║       ██║   ██║██║ ╚═╝ ██║███████╗
╚═╝      ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝       ╚═╝   ╚═╝╚═╝     ╚═╝╚══════╝
"""
print(f"{CSI}94m{focus_time}{CSI}0m")

# --- cargar o crear el config ---
if os.path.exists("config.json"):
    with open("config.json") as f:
        datos = json.load(f)
else:
    ojetivo_semanal = int(input("Weekly goal(in hours):"))
    datos = {"weekly goal": ojetivo_semanal, "sesiones": []}
    with open("config.json", "w") as f:
        json.dump(datos, f, indent=2)

# --- barra del progreso semanal ---
objetivo_segundos = datos["weekly goal"] * 3600
hechos = sum(s["duracion_segundos"] for s in datos.get("sesiones", []))
porcentajeSemanal = hechos / objetivo_segundos * 100

ancho = 77
llenos = int(ancho * (min(porcentajeSemanal, 100) / 100))
vacios = ancho - llenos
barra = "█" * llenos + "░" * vacios
print(f"{barra} {round(porcentajeSemanal, 1)}%\n")

# --- pedir la duracion ---
h = int(input("Hours: "))
print(f"{CSI}1A", end="")   # sube 1 línea
print(f"{CSI}K", end="")    # borra esa línea
m = int(input("Minutes: "))
print(f"{CSI}1A", end="")   # sube 1 línea
print(f"{CSI}K", end="")    # borra esa línea
total = h * 3600 + m * 60

# --- temporizador ---
for restante in range(total, -1, -1):
    porcentaje = (1 - (restante / total)) * 100
    h = restante // 3600
    m = (restante % 3600) // 60
    s = restante % 60
    ancho = 67
    llenos = int(ancho * (porcentaje / 100))
    vacios = ancho - llenos
    barra = "█" * llenos + "░" * vacios
    reloj = f"{h:02d}:{m:02d}:{s:02d}"
    print(f"\r{CSI}K{reloj: <10}{barra} {round(porcentaje, 0)}%", end="", flush=True)
    if restante != 0:
        time.sleep(1)

# --- guardar la sesion ---
with open("config.json") as f:
    datos = json.load(f)
sesion = {
    "fin": datetime.now().isoformat(timespec="seconds"),
    "duracion_segundos": total,
}
datos.setdefault("sesiones", []).append(sesion)
with open("config.json", "w") as f:
    json.dump(datos, f, indent=2)
