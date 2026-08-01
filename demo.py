import time

CSI = "\x1b["
print(f"{CSI}94mFocus time")
h = int(input("Hours: "))

print(f"{CSI}1A", end="")   # sube 1 línea
print(f"{CSI}K", end="")    # borra esa línea

m = int(input("Minutes: "))

print(f"{CSI}1A", end="")   # sube 1 línea
print(f"{CSI}K", end="")    # borra esa línea

total = h * 3600 + m * 60

inicio = time.perf_counter()
for restante in range(total, -1, -1):

    porcentaje=(1-(restante/total))*100
    h=restante//3600
    m=(restante%3600)//60
    s=restante%60


    ancho=20
    llenos = int(ancho*(porcentaje/100))
    vacios = int(ancho-llenos)
    barra = "█" * llenos + "░" * vacios


    print(f"\r{CSI}K{h:02d}:{m:02d}:{s:02d}{" ":20}{barra}{round(porcentaje, 0)}%", end="", flush=True)

    if restante != 0:
        time.sleep(1)

print(f"\nEsperados: {total}s  Reales: {time.perf_counter() - inicio:.2f}s")
