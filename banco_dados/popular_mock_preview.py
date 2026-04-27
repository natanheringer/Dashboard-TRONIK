"""
Povoa a base local com dados mock compatíveis com o preview atual.

Uso:
    python -m banco_dados.popular_mock_preview
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import Coleta, Coletor, Parceiro, Sensor, TipoColetor, TipoMaterial, TipoSensor
from banco_dados.seed_tipos import popular_tipos


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "sqlite:///tronik.db")
    engine = create_engine(database_url, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    popular_tipos(engine)

    caminho = Path(__file__).resolve().parent / "dados" / "sensores_mock.json"
    payload = json.loads(caminho.read_text(encoding="utf-8"))

    db = SessionLocal()
    try:
        parceiro = db.query(Parceiro).filter(Parceiro.nome == "Mock parceiro local").first()
        if parceiro is None:
            parceiro = Parceiro(nome="Mock parceiro local", ativo=True)
            db.add(parceiro)
            db.flush()

        tipo_material = db.query(TipoMaterial).first()
        tipo_sensor = db.query(TipoSensor).first()
        tipo_coletor = db.query(TipoColetor).first()

        existentes = {c.localizacao: c for c in db.query(Coletor).all()}
        mapa_por_id: dict[int, Coletor] = {}

        for item in payload["lixeiras"]:
            nome = item["localizacao"]
            status_raw = str(item.get("status", "OK")).upper()
            status = "MANUTENCAO" if "MANUT" in status_raw else "OK"
            coletor = existentes.get(nome)
            if coletor is None:
                coletor = Coletor(
                    localizacao=nome,
                    nivel_preenchimento=float(item["nivel_preenchimento"]),
                    status=status,
                    ultima_coleta=datetime.fromisoformat(item["ultima_coleta"]),
                    latitude=float(item["coordenadas"]["latitude"]),
                    longitude=float(item["coordenadas"]["longitude"]),
                    parceiro_id=parceiro.id,
                    tipo_material_id=tipo_material.id if tipo_material else None,
                )
                db.add(coletor)
                db.flush()
            mapa_por_id[int(item["id"])] = coletor

            if not coletor.sensores:
                db.add(
                    Sensor(
                        coletor_id=coletor.id,
                        tipo_sensor_id=tipo_sensor.id if tipo_sensor else None,
                        bateria=max(12.0, 82.0 - (int(item["id"]) * 7)),
                    )
                )

        db.flush()

        if db.query(Coleta).count() == 0:
            for row in payload["historico_coletas"][-80:]:
                coletor = mapa_por_id.get(int(row["id_lixeira"]))
                if coletor is None:
                    continue
                db.add(
                    Coleta(
                        coletor_id=coletor.id,
                        parceiro_id=parceiro.id,
                        tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
                        data_hora=datetime.fromisoformat(row["data_coleta"]),
                        volume_estimado=max(
                            0.0,
                            float(row.get("nivel_antes", 0)) - float(row.get("nivel_depois", 0)),
                        ),
                        tipo_operacao=row.get("tipo_coleta", "programada").title(),
                        km_percorrido=12.0 + (int(row["id_lixeira"]) * 1.5),
                        preco_combustivel=6.29,
                        lucro_por_kg=1.8,
                        emissao_mtr=False,
                    )
                )

        db.commit()
        print("Base local povoada com dados mock do preview.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
