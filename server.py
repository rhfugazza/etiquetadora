from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional
import json
import uuid
import subprocess
import os
import sys
from datetime import datetime

app = FastAPI()

API_KEY = "ROTATIVA-PRINT-2025"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(BASE_DIR, "queue")
PRINT_SCRIPT = os.path.join(BASE_DIR, "imprimir_lote.py")
LOG_FILE = os.path.join(BASE_DIR, "print_log")


class Job(BaseModel):
    nome: str
    quantidade: int
    etiquetas: int


class ReorderPayload(BaseModel):
    ordered_ids: List[str]


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida ou ausente")
    return True


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        # se log falhar, não derruba a API
        pass


def load_queue():
    # Garante que o arquivo exista e contenha uma lista válida
    if not os.path.exists(QUEUE_FILE):
        save_queue([])
        return []

    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                save_queue([])
                return []
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return parsed
            # se não for lista, reseta
            save_queue([])
            return []
    except Exception as e:
        log(f"ERRO load_queue: {e} (resetando fila)")
        save_queue([])
        return []


def save_queue(queue):
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"ERRO save_queue: {e}")
        raise HTTPException(status_code=500, detail="Falha ao salvar fila")


def run_print(job):
    if not os.path.exists(PRINT_SCRIPT):
        log(f"ERRO: imprimir_lote.py não encontrado em {PRINT_SCRIPT}")
        raise HTTPException(status_code=500, detail="Script de impressão não encontrado")

    cmd = [
        sys.executable,
        PRINT_SCRIPT,
        job["nome"],
        str(job["quantidade"]),
        str(job["etiquetas"]),
    ]

    log("Disparando impressão: " + " ".join(cmd))

    try:
        # DEVNULL evita travar por buffer de stdout/stderr
        p = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log(f"Processo iniciado PID={p.pid}")
        return p.pid
    except Exception as e:
        log(f"ERRO ao iniciar processo: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao iniciar impressão: {e}")


@app.get("/jobs", dependencies=[Depends(require_api_key)])
def list_jobs():
    return load_queue()


@app.post("/jobs", dependencies=[Depends(require_api_key)])
def add_job(job: Job):
    queue = load_queue()
    item = job.model_dump()
    item["id"] = str(uuid.uuid4())
    item["status"] = "pendente"
    queue.append(item)
    save_queue(queue)
    log(f"Job adicionado: {item['id']} | {item['nome']} | qtd={item['quantidade']} | etq={item['etiquetas']}")
    return item


@app.post("/jobs/clear", dependencies=[Depends(require_api_key)])
def clear_jobs():
    save_queue([])
    log("Fila limpa (clear)")
    return {"message": "Fila limpa com sucesso"}


@app.post("/jobs/reorder", dependencies=[Depends(require_api_key)])
def reorder_jobs(payload: ReorderPayload):
    queue = load_queue()
    by_id = {j.get("id"): j for j in queue if j.get("id")}

    # remove duplicados mantendo ordem
    seen = set()
    ordered_unique = []
    for _id in payload.ordered_ids:
        if _id and _id not in seen:
            seen.add(_id)
            ordered_unique.append(_id)

    new_queue = [by_id[_id] for _id in ordered_unique if _id in by_id]

    # mantém no final qualquer item que não veio no payload
    remaining = [j for j in queue if j.get("id") not in set(ordered_unique)]
    new_queue.extend(remaining)

    save_queue(new_queue)
    log(f"Fila reordenada: {len(new_queue)} itens")
    return {"message": "Fila reordenada", "count": len(new_queue)}


@app.post("/jobs/print-next", dependencies=[Depends(require_api_key)])
def print_next():
    queue = load_queue()
    if not queue:
        return {"message": "Fila vazia"}

    job = queue.pop(0)
    pid = run_print(job)
    save_queue(queue)
    log(f"Print-next: {job.get('id')} PID={pid}")
    return {"message": "Impressão disparada", "job": job, "pid": pid}


@app.post("/jobs/{job_id}/print", dependencies=[Depends(require_api_key)])
def print_specific(job_id: str):
    queue = load_queue()
    idx = next((i for i, j in enumerate(queue) if j.get("id") == job_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = queue.pop(idx)
    pid = run_print(job)
    save_queue(queue)
    log(f"Print-specific: {job.get('id')} PID={pid}")
    return {"message": "Impressão disparada", "job": job, "pid": pid}
