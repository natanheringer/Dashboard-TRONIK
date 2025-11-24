"""
Serializers - Dashboard-TRONIK
==============================
Converte modelos SQLAlchemy para dicionários JSON.
Centraliza toda a lógica de serialização.
"""

from typing import Dict, Optional
from banco_dados.modelos import Coletor, Coleta, Sensor, Notificacao


def coletor_para_dict(coletor: Coletor) -> Dict:
    """Converte um objeto Coletor para dicionário"""
    return {
        "id": coletor.id,
        "localizacao": coletor.localizacao,
        "nivel_preenchimento": coletor.nivel_preenchimento,
        "status": coletor.status,
        "ultima_coleta": coletor.ultima_coleta.isoformat() if coletor.ultima_coleta else None,
        "latitude": coletor.latitude,
        "longitude": coletor.longitude,
        "parceiro": {
            "id": coletor.parceiro.id,
            "nome": coletor.parceiro.nome
        } if coletor.parceiro else None,
        "tipo_material": {
            "id": coletor.tipo_material.id,
            "nome": coletor.tipo_material.nome
        } if coletor.tipo_material else None
    }


def coleta_para_dict(coleta: Coleta) -> Dict:
    """Converte um objeto Coleta para dicionário"""
    return {
        "id": coleta.id,
        "coletor_id": coleta.coletor_id,
        "data_hora": coleta.data_hora.isoformat() if coleta.data_hora else None,
        "volume_estimado": coleta.volume_estimado,
        "tipo_operacao": coleta.tipo_operacao,
        "km_percorrido": coleta.km_percorrido,
        "preco_combustivel": coleta.preco_combustivel,
        "lucro_por_kg": coleta.lucro_por_kg,
        "emissao_mtr": coleta.emissao_mtr,
        "tipo_coletor": {
            "id": coleta.tipo_coletor.id,
            "nome": coleta.tipo_coletor.nome
        } if coleta.tipo_coletor else None,
        "parceiro": {
            "id": coleta.parceiro.id,
            "nome": coleta.parceiro.nome
        } if coleta.parceiro else None,
        "coletor": {
            "id": coleta.coletor.id,
            "localizacao": coleta.coletor.localizacao
        } if coleta.coletor else None
    }


def sensor_para_dict(sensor: Sensor) -> Dict:
    """Converte um objeto Sensor para dicionário"""
    return {
        "id": sensor.id,
        "coletor_id": sensor.coletor_id,
        "bateria": sensor.bateria,
        "ultimo_ping": sensor.ultimo_ping.isoformat() if sensor.ultimo_ping else None,
        "tipo_sensor": {
            "id": sensor.tipo_sensor.id,
            "nome": sensor.tipo_sensor.nome
        } if sensor.tipo_sensor else None,
        "coletor": {
            "id": sensor.coletor.id,
            "localizacao": sensor.coletor.localizacao
        } if sensor.coletor else None
    }


def notificacao_para_dict(notificacao: Notificacao) -> Dict:
    """Converte um objeto Notificacao para dicionário"""
    return {
        "id": notificacao.id,
        "tipo": notificacao.tipo,
        "titulo": notificacao.titulo,
        "mensagem": notificacao.mensagem,
        "enviada": notificacao.enviada,
        "enviada_em": notificacao.enviada_em.isoformat() if notificacao.enviada_em else None,
        "lida": notificacao.lida,
        "lida_em": notificacao.lida_em.isoformat() if notificacao.lida_em else None,
        "criada_em": notificacao.criada_em.isoformat() if notificacao.criada_em else None,
        "coletor": {
            "id": notificacao.coletor.id,
            "localizacao": notificacao.coletor.localizacao
        } if notificacao.coletor else None,
        "sensor": {
            "id": notificacao.sensor.id,
            "bateria": notificacao.sensor.bateria
        } if notificacao.sensor else None
    }

