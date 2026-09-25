"""
Reproductor de audio para reproducción en tiempo real en consola.
Utiliza winsound de forma nativa en Windows sin dependencias externas pesadas.
"""

import os
import platform
import subprocess
from typing import Optional


def play_audio_file(audio_path: str, blocking: bool = True) -> bool:
    """
    Reproduce un archivo de audio WAV en los altavoces locales del usuario.
    Retorna True si la reproducción se inició exitosamente.
    """
    if not os.path.exists(audio_path):
        return False

    current_os = platform.system()

    # 1. Windows: Usar winsound nativo
    if current_os == "Windows":
        try:
            import winsound

            flags = winsound.SND_FILENAME
            if not blocking:
                flags |= winsound.SND_ASYNC
            winsound.PlaySound(audio_path, flags)
            return True
        except Exception as e:
            # Fallback a ffplay o powershell
            pass

    # 2. Intentar PowerShell SoundPlayer en Windows como respaldo secundario
    if current_os == "Windows":
        try:
            cmd = [
                "powershell",
                "-c",
                f"(New-Object Media.SoundPlayer '{audio_path}').PlaySync()",
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return True
        except Exception:
            pass

    # 3. macOS / Linux fallbacks (afplay, aplay, paplay)
    for player in ["afplay", "aplay", "paplay", "ffplay"]:
        try:
            cmd = [player, audio_path]
            if player == "ffplay":
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return True
        except FileNotFoundError:
            continue
        except Exception:
            pass

    return False
