"""
Detección de inactividad de teclado y ratón.

esta_inactivo(segundos) -> True si han pasado `segundos` sin tocar nada.

Los listeners de pynput se arrancan en la primera llamada y viven en hilos
daemon durante todo el programa. Nota: en Wayland pynput NO recibe eventos
globales; en ese caso hay que cambiar a la variante con evdev.
"""

import time

from pynput import keyboard, mouse

_ultimo = time.monotonic()
_iniciado = False


def _actividad(*_):
    global _ultimo
    _ultimo = time.monotonic()


def _iniciar():
    global _iniciado
    if _iniciado:
        return
    keyboard.Listener(on_press=_actividad).start()
    mouse.Listener(
        on_move=_actividad, on_click=_actividad, on_scroll=_actividad
    ).start()
    _iniciado = True


def marcar_actividad():
    """Registra actividad a mano (y arranca los listeners si hace falta).

    Sirve para reiniciar el contador al empezar un temporizador, y para
    contar como actividad las teclas leídas directamente de la terminal
    (útil en Wayland, donde pynput no ve los eventos globales).
    """
    _iniciar()
    _actividad()


def esta_inactivo(segundos=30):
    """True si han pasado `segundos` sin teclado ni ratón. False si no."""
    _iniciar()
    return (time.monotonic() - _ultimo) >= segundos


def segundos_inactivo():
    """Cuánto tiempo llevas sin tocar nada. Útil para depurar."""
    _iniciar()
    return time.monotonic() - _ultimo
