"""
Backend API local para la Interfaz Gráfica de Escritorio (Electron).
Provee endpoints REST para métricas de hardware, control de demonios,
estadísticas agregadas, gestión de perfiles, chat y síntesis de voz.
"""

from contextlib import asynccontextmanager
import datetime
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import psutil

# Asegurar importación de módulos core
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
STORAGE_DIR = os.path.join(ROOT_DIR, "storage")
AVATARS_DIR = os.path.join(STORAGE_DIR, "profiles", "avatars")

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.contracts.models import UserProfile
from core.twin.chat_session import DigitalTwinChat
from core.tts.cloner import F5TTSVoiceCloner
from core.db import sync_all, ProfilerRepository
from core.session_reconciler import is_session_active

logger = logging.getLogger("api_server")

DB_PATH = os.path.join(STORAGE_DIR, "profiler.db")
repo = ProfilerRepository(DB_PATH)

# Instancias compartidas en memoria
_chat_sessions: Dict[str, DigitalTwinChat] = {}
_voice_cloner: Optional[F5TTSVoiceCloner] = None
_background_job_status: Dict[str, Any] = {
    "is_running": False,
    "current_task": None,
    "last_run": None,
    "logs": [],
}


def get_voice_cloner() -> F5TTSVoiceCloner:
    global _voice_cloner
    if _voice_cloner is None:
        _voice_cloner = F5TTSVoiceCloner()
    return _voice_cloner


def get_hardware_metrics() -> Dict[str, Any]:
    """Obtiene métricas de CPU, RAM del sistema y GPU NVIDIA RTX 4070."""
    cpu_percent = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    gpu_metrics = {
        "available": False,
        "name": "NVIDIA GeForce RTX 4070",
        "utilization_percent": 0,
        "vram_used_mb": 0,
        "vram_total_mb": 12288,
        "temperature_c": 0,
    }

    try:
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name", "--format=csv,noheader,nounits"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            if len(parts) >= 4:
                gpu_metrics["available"] = True
                gpu_metrics["utilization_percent"] = int(parts[0])
                gpu_metrics["vram_used_mb"] = int(parts[1])
                gpu_metrics["vram_total_mb"] = int(parts[2])
                gpu_metrics["temperature_c"] = int(parts[3])
                if len(parts) >= 5:
                    gpu_metrics["name"] = parts[4]
    except Exception:
        pass

    return {
        "cpu_percent": cpu_percent,
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "ram_percent": ram.percent,
        "gpu": gpu_metrics,
    }


def get_daemons_status() -> Dict[str, Any]:
    """Verifica si el bot de Discord y el vigilante de IA están en ejecución."""
    recorder_running = False
    recorder_pid = None
    watcher_running = False
    watcher_pid = None

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or []).lower()
            # Grabador de Discord (node index.js en voice-recorder)
            if ("voice-recorder" in cmd or ("dist" in cmd and "index.js" in cmd)) and "server.py" not in cmd:
                recorder_running = True
                recorder_pid = proc.info["pid"]
            # Vigilante autónomo (main.py watch)
            if "main.py" in cmd and "watch" in cmd:
                watcher_running = True
                watcher_pid = proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Chequear lock file si el proceso fue lanzado externamente
    for lock_name in [".watcher.pid", "watch.pid"]:
        lock_file = os.path.join(STORAGE_DIR, lock_name)
        if not watcher_running and os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    saved_pid = int(f.read().strip())
                    if psutil.pid_exists(saved_pid):
                        watcher_running = True
                        watcher_pid = saved_pid
                        break
            except Exception:
                pass

    # Contar sesiones pendientes
    raw_dir = os.path.join(STORAGE_DIR, "raw_sessions")
    pending_count = 0
    if os.path.exists(raw_dir):
        for s in os.listdir(raw_dir):
            if s.startswith("."):
                continue
            sp = os.path.join(raw_dir, s)
            if os.path.isdir(sp):
                if is_session_active(sp):
                    continue
                tf = os.path.join(sp, "transcript.json")
                ad = os.path.join(sp, "audio")
                pf = os.path.join(ad, ".purged") if os.path.exists(ad) else None
                if not os.path.exists(tf) or (ad and os.path.exists(ad) and not os.path.exists(pf)):
                    pending_count += 1

    return {
        "recorder": {
            "active": recorder_running,
            "pid": recorder_pid,
        },
        "watcher": {
            "active": watcher_running,
            "pid": watcher_pid,
        },
        "pending_sessions_count": pending_count,
        "is_processing_batch": _background_job_status["is_running"],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(AVATARS_DIR, exist_ok=True)
    # Sincronizar automáticamente el almacenamiento hacia SQLite en el arranque
    try:
        sync_all(STORAGE_DIR, DB_PATH)
        logger.info("Base de datos SQLite sincronizada exitosamente.")
    except Exception as e:
        logger.error(f"Error sincronizando base de datos SQLite: {e}")
    yield
    # Limpieza al cerrar
    global _voice_cloner
    if _voice_cloner is not None:
        _voice_cloner.release()
        _voice_cloner = None


app = FastAPI(title="Discord AI Profiler Local API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# 1. Endpoints de Estado de Hardware y Demonios
# ==============================================================================

@app.get("/api/status")
def get_system_status():
    """Retorna estado completo de hardware, VRAM y procesos en ejecución."""
    return {
        "timestamp": time.time(),
        "hardware": get_hardware_metrics(),
        "daemons": get_daemons_status(),
        "background_job": _background_job_status,
    }


@app.post("/api/daemon/recorder/toggle")
def toggle_recorder():
    """Inicia o detiene el proceso grabador de Discord de forma limpia."""
    status = get_daemons_status()["recorder"]
    if status["active"]:
        stop_file = os.path.join(STORAGE_DIR, ".recorder_stop")
        try:
            with open(stop_file, "w", encoding="utf-8") as f:
                f.write("stop")
            p = psutil.Process(status["pid"])
            # Esperar hasta 4s a que el bot cierre streams de audio y notifique a Discord
            try:
                p.wait(timeout=4)
            except psutil.TimeoutExpired:
                # Si excede el tiempo, forzar detención de seguridad
                for child in p.children(recursive=True):
                    try:
                        child.terminate()
                    except Exception:
                        pass
                p.terminate()
                p.wait(timeout=2)
            return {"status": "stopped", "message": "Grabador de Discord desconectado y detenido limpiamente."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            if os.path.exists(stop_file):
                try:
                    os.remove(stop_file)
                except Exception:
                    pass
    else:
        # Iniciar grabador
        recorder_dir = os.path.abspath(os.path.join(ROOT_DIR, "services", "voice-recorder"))
        entrypoint = os.path.join(recorder_dir, "dist", "src", "index.js")
        if not os.path.exists(entrypoint):
            raise HTTPException(status_code=500, detail="dist/src/index.js no existe. Compila con npm run build.")
        try:
            log_path = os.path.join(STORAGE_DIR, "recorder.log")
            log_file = open(log_path, "a", encoding="utf-8")
            node_bin = shutil.which("node") or "node"
            proc = subprocess.Popen(
                [node_bin, os.path.join("dist", "src", "index.js")],
                cwd=recorder_dir,
                stdout=log_file,
                stderr=log_file,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            time.sleep(0.5)
            return {"status": "started", "message": f"Grabador de Discord iniciado (PID {proc.pid})."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/daemon/watcher/toggle")
def toggle_watcher():
    """Inicia o detiene el proceso vigilante de IA."""
    status = get_daemons_status()["watcher"]
    if status["active"]:
        try:
            p = psutil.Process(status["pid"])
            for child in p.children(recursive=True):
                try:
                    child.terminate()
                except Exception:
                    pass
            p.terminate()
            p.wait(timeout=3)
            for lock_name in [".watcher.pid", "watch.pid"]:
                lock_file = os.path.join(STORAGE_DIR, lock_name)
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                    except Exception:
                        pass
            return {"status": "stopped", "message": "Vigilante de IA detenido."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        try:
            logs_dir = os.path.join(STORAGE_DIR, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_file = open(os.path.join(logs_dir, "watcher.log"), "a", encoding="utf-8")
            subprocess.Popen(
                [sys.executable, "-u", "main.py", "watch"],
                cwd=BASE_DIR,
                stdout=log_file,
                stderr=log_file,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            return {"status": "started", "message": "Vigilante de IA iniciado en segundo plano."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


def _run_batch_process():
    global _background_job_status
    _background_job_status["is_running"] = True
    _background_job_status["current_task"] = "Procesando todas las sesiones pendientes..."
    try:
        cmd = [sys.executable, "main.py", "process-all"]
        proc = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        try:
            sync_all(STORAGE_DIR, DB_PATH)
        except Exception:
            pass
        _background_job_status["last_run"] = {
            "success": proc.returncode == 0,
            "stdout": proc.stdout[-500:] if proc.stdout else "",
            "stderr": proc.stderr[-500:] if proc.stderr else "",
            "finished_at": time.time(),
        }
    except Exception as e:
        _background_job_status["last_run"] = {
            "success": False,
            "error": str(e),
            "finished_at": time.time(),
        }
    finally:
        _background_job_status["is_running"] = False
        _background_job_status["current_task"] = None


@app.post("/api/daemon/process-all")
def trigger_process_all(background_tasks: BackgroundTasks):
    """Dispara el procesamiento en lote en segundo plano de todas las sesiones acumuladas."""
    if _background_job_status["is_running"]:
        return {"status": "busy", "message": "Ya hay un proceso en lote ejecutándose en la GPU."}

    background_tasks.add_task(_run_batch_process)
    return {"status": "accepted", "message": "Procesamiento en lote iniciado en la GPU."}


def get_all_profile_paths() -> List[str]:
    """Retorna todas las rutas a archivos de perfil existentes en storage."""
    profiles_dir = os.path.join(STORAGE_DIR, "profiles")
    paths = []
    if not os.path.exists(profiles_dir):
        return paths
    for entry in os.listdir(profiles_dir):
        full_p = os.path.join(profiles_dir, entry)
        if os.path.isdir(full_p) and entry != "avatars":
            sub_pf = os.path.join(full_p, "profile.json")
            if os.path.exists(sub_pf):
                paths.append(sub_pf)
        elif entry.endswith(".json") and not entry.startswith("."):
            paths.append(full_p)
    return paths


def find_profile_path(user_id_or_name: str) -> Optional[str]:
    """Busca el archivo de perfil por ID, username, display_name o apodo."""
    target = user_id_or_name.lower().strip()
    
    # 1. Búsqueda directa por directorio o archivo
    p1 = os.path.join(STORAGE_DIR, "profiles", user_id_or_name, "profile.json")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(STORAGE_DIR, "profiles", f"{user_id_or_name}.json")
    if os.path.exists(p2):
        return p2

    # 2. Búsqueda en el contenido de cada perfil
    for pf in get_all_profile_paths():
        try:
            with open(pf, "r", encoding="utf-8") as f:
                d = json.load(f)
                uid = str(d.get("user_id", "")).lower()
                uname = str(d.get("username", "")).lower()
                dname = str(d.get("display_name", "") or "").lower()
                nicks = [str(n).lower() for n in d.get("nicknames", [])]
                if target in (uid, uname, dname) or target in nicks:
                    return pf
        except Exception:
            pass
    return None


# ==============================================================================
# 2. Endpoints de Estadísticas Globales y Resumen
# ==============================================================================

@app.get("/api/stats/global")
def get_global_stats():
    """Genera estadísticas consolidadas a partir de la base de datos SQLite."""
    return repo.get_global_stats()


# ==============================================================================
# 3. Endpoints de Usuarios, Fichas y Vocabulario
# ==============================================================================

@app.get("/api/users")
def list_users():
    """Lista todos los perfiles de usuario disponibles desde SQLite."""
    return repo.list_users()


@app.get("/api/users/{user_id}")
def get_user_detail(user_id: str):
    """Devuelve la ficha técnica psicológica y sociolingüística completa de un usuario desde SQLite."""
    detail = repo.get_user_detail(user_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Usuario {user_id} no encontrado")
    return detail


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    nicknames: Optional[List[str]] = None
    notes: Optional[List[str]] = None
    role: Optional[str] = None
    humor: Optional[str] = None


@app.post("/api/users/{user_id}")
def update_user_profile(user_id: str, payload: UserUpdateRequest):
    """Actualiza apodos, notas de contexto, rol o nombre visible en SQLite y disco."""
    ok = repo.update_user_metadata(
        user_id=user_id,
        display_name=payload.display_name,
        nicknames=payload.nicknames,
        role=payload.role,
        humor=payload.humor,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Sincronizar archivo en disco si existe
    profile_path = find_profile_path(user_id)
    if profile_path and os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if payload.display_name is not None:
                data["display_name"] = payload.display_name.strip()
            if payload.nicknames is not None:
                data["nicknames"] = [n.strip() for n in payload.nicknames if n.strip()]
            if payload.role is not None:
                if "group_role" not in data:
                    data["group_role"] = {}
                data["group_role"]["primary_role"] = payload.role.strip()
            if payload.humor is not None:
                if "communication_style" not in data:
                    data["communication_style"] = {}
                data["communication_style"]["humor_type"] = payload.humor.strip()
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {"status": "success", "user_id": user_id}


@app.post("/api/users/{user_id}/avatar")
async def upload_user_avatar(user_id: str, file: UploadFile = File(...)):
    """Guarda una foto personalizada para el usuario de manera persistente."""
    os.makedirs(AVATARS_DIR, exist_ok=True)
    target_path = os.path.join(AVATARS_DIR, f"{user_id}.png")

    try:
        content = await file.read()
        with open(target_path, "wb") as f:
            f.write(content)
        return {
            "status": "success",
            "avatar_url": f"/api/users/{user_id}/avatar?t={int(time.time())}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar la imagen: {e}")


@app.get("/api/users/{user_id}/avatar")
def get_user_avatar(user_id: str):
    """Devuelve la imagen de avatar del usuario."""
    avatar_path = os.path.join(AVATARS_DIR, f"{user_id}.png")
    if not os.path.exists(avatar_path):
        raise HTTPException(status_code=404, detail="Avatar no encontrado")
    return FileResponse(avatar_path, media_type="image/png")


# ==============================================================================
# 4. Endpoints de Chat con el Gemelo Digital
# ==============================================================================

class ChatMessageRequest(BaseModel):
    message: str
    backend: Optional[str] = "auto"  # "auto", "gemini", o "llama"


@app.post("/api/chat/{user_id}")
def send_chat_message(user_id: str, payload: ChatMessageRequest):
    """Envía un mensaje al Gemelo Digital del amigo y devuelve su respuesta conversacional limpia."""
    global _chat_sessions

    # Cargar perfil
    profile_path = find_profile_path(user_id)
    if not profile_path or not os.path.exists(profile_path):
        raise HTTPException(status_code=404, detail="Perfil de usuario no encontrado")

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = UserProfile.model_validate_json(f.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validando perfil: {e}")

    session_key = f"{user_id}_{payload.backend}"
    if session_key not in _chat_sessions:
        _chat_sessions[session_key] = DigitalTwinChat(
            profile=profile,
            base_storage_dir=STORAGE_DIR,
            backend=payload.backend,
        )

    chat = _chat_sessions[session_key]
    reply = chat.send_message(payload.message)

    return {
        "user_id": user_id,
        "reply": reply,
        "history": chat.history,
    }


@app.post("/api/chat/{user_id}/clear")
def clear_chat_history(user_id: str):
    """Reinicia la conversación con el gemelo digital."""
    global _chat_sessions
    keys_to_delete = [k for k in _chat_sessions.keys() if k.startswith(f"{user_id}_")]
    for k in keys_to_delete:
        del _chat_sessions[k]
    return {"status": "cleared", "user_id": user_id}


# ==============================================================================
# 5. Endpoint de Síntesis de Voz (TTS)
# ==============================================================================

class TTSRequest(BaseModel):
    text: str


@app.post("/api/tts/{user_id}")
def synthesize_speech(user_id: str, payload: TTSRequest):
    """Sintetiza una frase con la voz clonada del amigo usando F5-TTS."""
    cloner = get_voice_cloner()
    output_dir = os.path.join(STORAGE_DIR, "twin_outputs", user_id)
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = os.path.join(output_dir, f"gui_reply_{ts}.wav")

    try:
        wav_file = cloner.clone_for_user(
            user_id=user_id,
            target_text=payload.text,
            base_storage_dir=STORAGE_DIR,
            output_path=out_path,
        )
        return FileResponse(wav_file, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en síntesis TTS: {e}")


if __name__ == "__main__":
    import uvicorn
    import datetime
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
