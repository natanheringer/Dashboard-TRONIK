import sqlite3
import urllib.request
import urllib.error
import json
from time import sleep

def seed_db():
    conn = sqlite3.connect('tronik.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO coletores (id, localizacao, nivel_preenchimento, status) VALUES (1, 'Rua Teste 123', 0.0, 'OK')")
    cursor.execute("INSERT OR IGNORE INTO sensores (id, coletor_id, bateria) VALUES (1, 1, 100.0)")
    conn.commit()
    conn.close()

seed_db()
url = "http://localhost:5000/api/sensor/telemetria"
data = {
    "api_key": "tronik-isu-mvp-2026",
    "sensor_id": 1,
    "coletor_id": 1,
    "nivel_preenchimento": 85.0,
    "bateria": 15.0,
    "leituras_tof": [75.0, 80.0, 78.0]
}

def send_telemetry():
    print("Enviando telemetria...")
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            print("Status code:", response.status)
            print("Response:", response.read().decode('utf-8'))
            return True
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code)
        print("Response:", e.read().decode('utf-8'))
        return False
    except urllib.error.URLError as e:
        print("Connection error:", e.reason)
        return False

def check_db():
    print("\nVerificando Banco de Dados...")
    conn = sqlite3.connect('tronik.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Verificar Coletor
    cursor.execute("SELECT status FROM coletores WHERE id = 1")
    row = cursor.fetchone()
    if row:
        print(f"Status do Coletor 1: {row['status']}")
    else:
        print("Coletor 1 não encontrado.")
        
    # Verificar Notificações relacionadas ao coletor (assumindo que seja 'coletor_id' ou 'lixeira_id')
    # O campo exato de chave secundária precisa ser verificado, vou consultar a tabela notificacoes primeiro
    cursor.execute("PRAGMA table_info(notificacoes)")
    cols = [c['name'] for c in cursor.fetchall()]
    
    col_id = 'coletor_id' if 'coletor_id' in cols else ('lixeira_id' if 'lixeira_id' in cols else None)
    
    if col_id:
        cursor.execute(f"SELECT tipo, mensagem FROM notificacoes WHERE {col_id} = 1")
        rows = cursor.fetchall()
        print(f"Total de notificações para o Coletor 1: {len(rows)}")
        for r in rows:
            print(f"- Tipo: {r['tipo']} | Mensagem: {r['mensagem']}")
    else:
        print("Coluna referenciando o coletor não encontrada.")
            
    conn.close()

print("--- PRIMEIRA EXECUÇÃO ---")
success = send_telemetry()
if success:
    sleep(1) # wait for async operations if any
    check_db()

print("\n--- SEGUNDA EXECUÇÃO (Teste de Duplicação) ---")
success2 = send_telemetry()
if success2:
    sleep(1)
    check_db()
