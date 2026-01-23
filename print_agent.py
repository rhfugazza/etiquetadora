import argparse
import json
import os
import sys
import time
import subprocess
from urllib import request, error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "agent_config.json")
PRINT_SCRIPT = os.path.join(BASE_DIR, "imprimir_lote.py")


def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(
            "agent_config.json nao encontrado. Copie o exemplo e preencha as configuracoes."
        )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    api_base_url = os.getenv("API_BASE_URL", data.get("api_base_url"))
    api_key = os.getenv("API_KEY", data.get("api_key"))
    agent_id = os.getenv("AGENT_ID", data.get("agent_id"))
    poll_seconds = int(os.getenv("POLL_SECONDS", data.get("poll_seconds", 5)))
    timeout_seconds = int(os.getenv("REQUEST_TIMEOUT", data.get("request_timeout_seconds", 15)))

    if not api_base_url or not api_key:
        raise ValueError("api_base_url e api_key sao obrigatorios")

    return {
        "api_base_url": api_base_url.rstrip("/"),
        "api_key": api_key,
        "agent_id": agent_id or os.getenv("COMPUTERNAME", "agent"),
        "poll_seconds": poll_seconds,
        "timeout_seconds": timeout_seconds,
    }


def http_json(method, url, api_key, payload=None, timeout=15):
    data = None
    headers = {"X-API-Key": api_key}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return None
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"raw": body}
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except error.URLError as e:
        raise RuntimeError(f"Network error: {e}")


def claim_job(config):
    url = f"{config['api_base_url']}/agent/claim"
    payload = {"agent_id": config["agent_id"]}
    response = http_json(
        "POST",
        url,
        config["api_key"],
        payload=payload,
        timeout=config["timeout_seconds"],
    )
    if not isinstance(response, dict):
        return None
    if response.get("id"):
        return response
    return None


def report_job(config, job_id, status, error_message=None):
    url = f"{config['api_base_url']}/agent/report"
    payload = {"job_id": job_id, "status": status}
    if error_message:
        payload["error"] = error_message
    return http_json(
        "POST",
        url,
        config["api_key"],
        payload=payload,
        timeout=config["timeout_seconds"],
    )


def run_print(job):
    if not os.path.exists(PRINT_SCRIPT):
        return False, f"print script nao encontrado: {PRINT_SCRIPT}"

    cmd = [
        sys.executable,
        PRINT_SCRIPT,
        job.get("nome", ""),
        str(job.get("quantidade", "")),
        str(job.get("etiquetas", "")),
    ]

    result = subprocess.run(
        cmd,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        if not err:
            err = f"exit code {result.returncode}"
        return False, err

    return True, ""


def parse_args():
    parser = argparse.ArgumentParser(description="Print agent")
    parser.add_argument("--once", action="store_true", help="processa um job e sai")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        config = load_config(CONFIG_FILE)
    except Exception as e:
        print(f"Config error: {e}")
        return 1

    print(f"Agent started. Base URL: {config['api_base_url']}")

    while True:
        try:
            job = claim_job(config)
        except Exception as e:
            print(f"Claim error: {e}")
            if args.once:
                return 1
            time.sleep(config["poll_seconds"])
            continue

        if not job:
            if args.once:
                return 0
            time.sleep(config["poll_seconds"])
            continue

        print(f"Printing job {job.get('id')} - {job.get('nome')}")
        ok, err = run_print(job)
        status = "success" if ok else "failed"

        try:
            report_job(config, job.get("id"), status, err)
        except Exception as e:
            print(f"Report error: {e}")
            if args.once:
                return 1

        if not ok:
            print(f"Print failed: {err}")
            if args.once:
                return 1

        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
