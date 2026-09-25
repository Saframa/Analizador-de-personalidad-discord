"""
Diagnóstico de Entorno de Aceleración por GPU (CUDA / PyTorch)
Verifica la disponibilidad de la GPU NVIDIA (GeForce RTX 4070),
capacidades FP16 y memoria VRAM disponible.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def check_cuda() -> bool:
    print("=" * 60)
    print("[CUDA CHECK] VERIFICACION DE ACELERACION CUDA / PYTORCH")
    print("=" * 60)

    try:
        import torch
    except ImportError:
        print("❌ Error: PyTorch no está instalado.")
        return False

    print(f"Versión de PyTorch: {torch.__version__}")
    print(f"Versión de CUDA compilada en PyTorch: {torch.version.cuda}")

    cuda_available = torch.cuda.is_available()
    print(f"¿CUDA disponible?: {cuda_available}")

    if not cuda_available:
        print("❌ No se detectó soporte para GPU CUDA en este entorno.")
        return False

    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    props = torch.cuda.get_device_properties(0)
    total_vram_gb = props.total_memory / (1024 ** 3)

    print(f"Dispositivos CUDA detectados: {device_count}")
    print(f"GPU principal (Device 0): {device_name}")
    print(f"Compute Capability: {capability[0]}.{capability[1]}")
    print(f"VRAM Total: {total_vram_gb:.2f} GB")

    # Prueba de tensor en FP16 sobre CUDA (Tensor Cores)
    try:
        print("\n[TEST] Probando operaciones en FP16 (Tensor Cores)...")
        x = torch.randn(1024, 1024, dtype=torch.float16, device="cuda")
        y = torch.matmul(x, x)
        torch.cuda.synchronize()
        allocated_mb = torch.cuda.memory_allocated(0) / (1024 ** 2)
        print(f"[OK] Operacion FP16 ejecutada con exito. Memoria asignada: {allocated_mb:.2f} MB")
        del x, y
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"[ERROR] Error al ejecutar operaciones en GPU: {e}")
        return False

    print("=" * 60)
    print("[SUCCESS] Entorno CUDA verificado y listo para STT y curacion.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = check_cuda()
    sys.exit(0 if success else 1)
