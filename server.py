from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional
import json
import uuid
import os
from datetime import datetime

app = FastAPI()

API_KEY = os.getenv("API_KEY", "ROTATIVA-PRINT-2025")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.getenv("QUEUE_FILE", os.path.join(BASE_DIR, "queue"))
PRINT_QUEUE_FILE = os.getenv("PRINT_QUEUE_FILE", os.path.join(BASE_DIR, "print_queue"))
INFLIGHT_FILE = os.getenv("INFLIGHT_FILE", os.path.join(BASE_DIR, "inflight"))
LOG_FILE = os.getenv("LOG_FILE", os.path.join(BASE_DIR, "print_log"))


class Job(BaseModel):
    nome: str
    quantidade: int
    etiquetas: int


class ReorderPayload(BaseModel):
    ordered_ids: List[str]


class AgentClaim(BaseModel):
    agent_id: Optional[str] = None


class AgentReport(BaseModel):
    job_id: str
    status: str
    error: Optional[str] = None


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key invalida ou ausente")
    return True


def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str):
    ts = now_ts()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        # se log falhar, nao derruba a API
        pass


def load_list_file(path, label):
    # Garante que o arquivo exista e contenha uma lista valida
    if not os.path.exists(path):
        save_list_file(path, [], label)
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                save_list_file(path, [], label)
                return []
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return parsed
            # se nao for lista, reseta
            save_list_file(path, [], label)
            return []
    except Exception as e:
        log(f"ERRO load_{label}: {e} (resetando)")
        save_list_file(path, [], label)
        return []


def save_list_file(path, data, label):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"ERRO save_{label}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao salvar dados")


def load_queue():
    return load_list_file(QUEUE_FILE, "queue")


def save_queue(queue):
    save_list_file(QUEUE_FILE, queue, "queue")


def load_print_queue():
    return load_list_file(PRINT_QUEUE_FILE, "print_queue")


def save_print_queue(queue):
    save_list_file(PRINT_QUEUE_FILE, queue, "print_queue")


def load_inflight():
    return load_list_file(INFLIGHT_FILE, "inflight")


def save_inflight(queue):
    save_list_file(INFLIGHT_FILE, queue, "inflight")


def queue_print_request(job, requested_by=None):
    print_queue = load_print_queue()
    job["status"] = "requested"
    job["requested_at"] = now_ts()
    if requested_by:
        job["requested_by"] = requested_by
    print_queue.append(job)
    save_print_queue(print_queue)


def pop_job_by_id(queue, job_id):
    idx = next((i for i, j in enumerate(queue) if j.get("id") == job_id), None)
    if idx is None:
        return None
    return queue.pop(idx)


def resolve_agent_id(payload: Optional[AgentClaim], x_agent_id: Optional[str]):
    if payload and payload.agent_id:
        return payload.agent_id
    if x_agent_id:
        return x_agent_id
    return "unknown"


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
    save_print_queue([])
    log("Fila limpa (queue + print_queue)")
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

    # mantem no final qualquer item que nao veio no payload
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
    queue_print_request(job, requested_by="print-next")
    save_queue(queue)
    log(f"Print-next requested: {job.get('id')}")
    return {"message": "Impressao solicitada", "job": job}


@app.post("/jobs/{job_id}/print", dependencies=[Depends(require_api_key)])
def print_specific(job_id: str):
    queue = load_queue()
    job = pop_job_by_id(queue, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job nao encontrado")

    queue_print_request(job, requested_by="print-specific")
    save_queue(queue)
    log(f"Print-specific requested: {job.get('id')}")
    return {"message": "Impressao solicitada", "job": job}


@app.post("/agent/claim", dependencies=[Depends(require_api_key)])
def agent_claim(payload: Optional[AgentClaim] = None, x_agent_id: Optional[str] = Header(default=None)):
    agent_id = resolve_agent_id(payload, x_agent_id)
    print_queue = load_print_queue()
    if not print_queue:
        return {"message": "Sem solicitacoes"}

    job = print_queue.pop(0)
    job["status"] = "printing"
    job["claimed_at"] = now_ts()
    job["agent_id"] = agent_id
    save_print_queue(print_queue)

    inflight = load_inflight()
    inflight.append(job)
    save_inflight(inflight)

    log(f"Claim: {job.get('id')} agent={agent_id}")
    return job


@app.post("/agent/report", dependencies=[Depends(require_api_key)])
def agent_report(payload: AgentReport):
    inflight = load_inflight()
    job = pop_job_by_id(inflight, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job nao encontrado em inflight")

    status = payload.status.strip().lower()
    if status == "success":
        job["status"] = "printed"
        job["printed_at"] = now_ts()
        save_inflight(inflight)
        log(f"Printed: {job.get('id')} agent={job.get('agent_id')}")
        return {"message": "Reportado sucesso"}

    if status in {"failed", "error", "requeue"}:
        job["status"] = "failed"
        job["failed_at"] = now_ts()
        if payload.error:
            job["error"] = payload.error
        save_inflight(inflight)

        queue = load_queue()
        queue.append(job)
        save_queue(queue)

        log(f"Print failed: {job.get('id')} requeued")
        return {"message": "Reportado erro, reencaminhado"}

    raise HTTPException(status_code=400, detail="Status invalido")
