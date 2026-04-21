"""
Smoke test manual para o endpoint /api/sensor/telemetria.

USO
---
Com o servidor rodando (python app.py, porta 5000 por padrao):

    python scripts/enviar_telemetria_manual.py

O que faz
---------
1. Garante que existe um Coletor (id=1) e um Sensor (id=1) no SQLite local (tronik.db).
2. Envia um payload de telemetria simulando o ESP32 (nivel 85%, bateria 15%).
3. Imprime a resposta da API.
4. Verifica diretamente no SQLite se o Coletor mudou de status e se foram
   geradas Notificacoes (sem duplicata na mesma janela de 24h).
5. Repete o envio para validar que a regra anti-duplicata esta funcionando.

Nao e um teste pytest - e um smoke test manual, rapido, para validar que o
pipeline (HTTP -> Flask -> SQLAlchemy -> SQLite -> Notificacoes) esta integro
apos alteracoes. Os testes automatizados vivem em tests/.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from time import sleep

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "tronik.db"
URL = "http://localhost:5000/api/sensor/telemetria"

PAYLOAD = {
    "api_key": "tronik-isu-mvp-2026",
    "sensor_id": 1,
    "coletor_id": 1,
    "nivel_preenchimento": 85.0,
    "bateria": 15.0,
    "leituras_tof": [75.0, 80.0, 78.0],
}


def garantir_seed() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO coletores (id, localizacao, nivel_preenchimento, status) "
            "VALUES (1, 'Rua Teste 123', 0.0, 'OK')"
        )
        cur.execute(
            "INSERT OR IGNORE INTO sensores (id, coletor_id, bateria) VALUES (1, 1, 100.0)"
        )
        conn.commit()
    finally:
        conn.close()


def enviar() -> bool:
    print("Enviando telemetria...")
    req = urllib.request.Request(
        URL,
        data=json.dumps(PAYLOAD).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"  status: {resp.status}")
            print(f"  body:   {resp.read().decode('utf-8')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  HTTPError {e.code}: {e.read().decode('utf-8')}")
        return False
    except urllib.error.URLError as e:
        print(f"  URLError: {e.reason}")
        return False


def verificar_db() -> None:
    print("Verificando banco...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, nivel_preenchimento FROM coletores WHERE id = 1")
        row = cur.fetchone()
        if row:
            print(f"  coletor#1 status={row['status']} nivel={row['nivel_preenchimento']}")
        cur.execute(
            "SELECT tipo, mensagem FROM notificacoes WHERE coletor_id = 1 "
            "ORDER BY criada_em DESC"
        )
        notifs = cur.fetchall()
        print(f"  notificacoes: {len(notifs)}")
        for n in notifs:
            print(f"    - [{n['tipo']}] {n['mensagem']}")
    finally:
        conn.close()


def main() -> int:
    if not DB_PATH.exists():
        print(f"[erro] banco nao encontrado em {DB_PATH}. Rode `python app.py` ao menos uma vez.")
        return 2
    garantir_seed()

    print("--- PRIMEIRA EXECUCAO ---")
    if not enviar():
        return 1
    sleep(0.3)
    verificar_db()

    print("\n--- SEGUNDA EXECUCAO (anti-duplicata em 24h) ---")
    if not enviar():
        return 1
    sleep(0.3)
    verificar_db()
    return 0


if __name__ == "__main__":
    sys.exit(main())
