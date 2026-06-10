"""
Rotas de Sensores - Dashboard-TRONIK
====================================
Endpoints para operações CRUD de sensores.
"""

import secrets
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy.orm import joinedload

from banco_dados.modelos import Sensor
from banco_dados.seguranca import validar_sensor
from banco_dados.serializers import (
    coletor_para_dict,
    notificacao_para_dict,
    sensor_para_dict,
)
from banco_dados.telemetria_auth import validar_telemetria
from banco_dados.utils import utc_now_naive
from banco_dados.utils.cache import obter_cache
from banco_dados.utils.erros import (
    ErroNaoEncontrado,
    ErroValidacao,
    tratar_erro_api,
)
from banco_dados.utils.logger import obter_logger
from rotas.api import decorators
from rotas.api.decorators import admin_required, get_db

logger = obter_logger(__name__)

# Criar blueprint
sensores_bp = Blueprint('sensores', __name__)


@sensores_bp.route('/sensores', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def listar_sensores():
    """Endpoint para listar todos os sensores com filtros opcionais"""
    db = get_db()
    try:
        query = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        )

        # Filtros opcionais
        coletor_id = request.args.get('coletor_id', type=int)
        tipo_sensor_id = request.args.get('tipo_sensor_id', type=int)
        bateria_min = request.args.get('bateria_min', type=float)
        bateria_max = request.args.get('bateria_max', type=float)

        if coletor_id:
            query = query.filter(Sensor.coletor_id == coletor_id)
        if tipo_sensor_id:
            query = query.filter(Sensor.tipo_sensor_id == tipo_sensor_id)
        if bateria_min is not None:
            query = query.filter(Sensor.bateria >= bateria_min)
        if bateria_max is not None:
            query = query.filter(Sensor.bateria <= bateria_max)

        sensores = query.all()
        resultado = [sensor_para_dict(s) for s in sensores]
        return jsonify(resultado)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor/<int:sensor_id>', methods=['GET'])
@login_required
def obter_sensor(sensor_id):
    """Endpoint para obter um sensor específico"""
    db = get_db()
    try:
        sensor = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == sensor_id).first()

        if not sensor:
            raise ErroNaoEncontrado("Sensor", sensor_id)

        return jsonify(sensor_para_dict(sensor))
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor', methods=['POST'])
@login_required
@decorators.rate_limit("10 per minute")
def criar_sensor():
    """Endpoint para criar um novo sensor"""
    db = get_db()
    try:
        from banco_dados.utils.validacao import sanitizar_dados_entrada, validar_dados_requisicao

        dados = request.get_json()
        dados = validar_dados_requisicao(dados)

        # Sanitizar dados de entrada (sensores geralmente não têm strings, mas por segurança)
        dados = sanitizar_dados_entrada(dados, [])

        # Validar dados
        erros = validar_sensor(dados, criar=True, db=db)
        if erros:
            raise ErroValidacao("Erros de validação", {"detalhes": erros})

        # Criar novo sensor (token opaco para telemetria; mostrado só nesta resposta)
        novo_sensor = Sensor(
            coletor_id=dados['coletor_id'],
            tipo_sensor_id=dados.get('tipo_sensor_id'),
            bateria=dados.get('bateria', 100.0),
            ultimo_ping=utc_now_naive(),
            api_token=secrets.token_urlsafe(32)[:128],
        )

        db.add(novo_sensor)
        db.commit()
        db.refresh(novo_sensor)

        # Carregar relacionamentos
        novo_sensor = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == novo_sensor.id).first()

        out = sensor_para_dict(novo_sensor)
        out["api_token"] = novo_sensor.api_token
        return jsonify(out), 201
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor/<int:sensor_id>', methods=['PUT'])
@login_required
@decorators.rate_limit("20 per minute")
def atualizar_sensor(sensor_id):
    """Endpoint para atualizar um sensor"""
    db = get_db()
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise ErroNaoEncontrado("Sensor", sensor_id)

        from banco_dados.utils.validacao import sanitizar_dados_entrada, validar_dados_requisicao

        dados = request.get_json()
        dados = validar_dados_requisicao(dados)

        # Sanitizar dados de entrada
        dados = sanitizar_dados_entrada(dados, [])

        # Validar dados
        erros = validar_sensor(dados, criar=False, db=db)
        if erros:
            raise ErroValidacao("Erros de validação", {"detalhes": erros})

        # Atualizar campos
        if 'coletor_id' in dados:
            sensor.coletor_id = dados['coletor_id']
        if 'tipo_sensor_id' in dados:
            sensor.tipo_sensor_id = dados['tipo_sensor_id']
        if 'bateria' in dados:
            sensor.bateria = dados['bateria']
        if 'ultimo_ping' in dados and dados['ultimo_ping']:
            try:
                sensor.ultimo_ping = datetime.fromisoformat(dados['ultimo_ping'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                sensor.ultimo_ping = utc_now_naive()

        db.commit()
        db.refresh(sensor)

        # Carregar relacionamentos
        sensor = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == sensor_id).first()

        return jsonify(sensor_para_dict(sensor))
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor/<int:sensor_id>', methods=['DELETE'])
@admin_required
def deletar_sensor(sensor_id):
    """Endpoint para deletar um sensor (apenas admin)"""
    db = get_db()
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise ErroNaoEncontrado("Sensor", sensor_id)

        db.delete(sensor)
        db.commit()

        return jsonify({"mensagem": "Sensor deletado com sucesso"}), 200
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()

# --------------------------------------------------------------------------
# Constantes de regra de negocio (centralizar facilita ajuste futuro)
# --------------------------------------------------------------------------
LIMIAR_NIVEL_CHEIO = 80.0   # % a partir do qual o coletor vira 'CHEIA'
LIMIAR_BATERIA_BAIXA = 20.0 # % abaixo do qual vira alerta 'bateria_baixa'
JANELA_DEDUP_HORAS = 24     # nao recriar a mesma notificacao dentro desse periodo


@sensores_bp.route("/sensor/telemetria", methods=["POST"])
@decorators.rate_limit("100 per minute")
def receber_telemetria():
    """Recebe telemetria do ESP32 e persiste estado + notificacoes.

    - Valida o payload com `TelemetriaIn` (Pydantic v2) antes de tocar no DB.
    - Atualiza nivel do Coletor e bateria/ultimo_ping do Sensor.
    - Gera notificacoes (`lixeira_cheia`, `bateria_baixa`) com dedup por 24h.
    - Resposta tipada por `TelemetriaOut`.
    """
    from datetime import timedelta

    from banco_dados.contratos import TelemetriaIn, TelemetriaOut, parse_ou_erro
    from banco_dados.modelos import Coletor, Notificacao
    from banco_dados.notificacoes import criar_notificacao

    db = get_db()
    try:
        payload = parse_ou_erro(TelemetriaIn, request.get_json(silent=True))

        coletor = db.query(Coletor).filter(Coletor.id == payload.coletor_id).first()
        sensor = db.query(Sensor).filter(Sensor.id == payload.sensor_id).first()
        if not coletor:
            raise ErroNaoEncontrado("Coletor", payload.coletor_id)
        if not sensor:
            raise ErroNaoEncontrado("Sensor", payload.sensor_id)
        if sensor.coletor_id != coletor.id:
            raise ErroValidacao(
                "sensor_id nao pertence ao coletor_id informado",
                {"detalhes": {"coletor_id": payload.coletor_id, "sensor_id": payload.sensor_id}},
            )

        validar_telemetria(sensor, payload.api_key)

        notificacoes = []
        limite_tempo = utc_now_naive() - timedelta(hours=JANELA_DEDUP_HORAS)

        coletor.nivel_preenchimento = payload.nivel_preenchimento
        if payload.nivel_preenchimento > LIMIAR_NIVEL_CHEIO:
            if coletor.status != "QUEBRADA":
                coletor.status = "CHEIA"
            ja_existe = (
                db.query(Notificacao)
                .filter(
                    Notificacao.coletor_id == coletor.id,
                    Notificacao.tipo == "lixeira_cheia",
                    Notificacao.criada_em >= limite_tempo,
                )
                .first()
            )
            if not ja_existe:
                notificacoes.append(criar_notificacao(
                    db=db,
                    tipo="lixeira_cheia",
                    titulo=f"Coletor #{coletor.id} - Nivel Alto",
                    mensagem=(
                        f"O coletor em {coletor.localizacao} esta com "
                        f"{coletor.nivel_preenchimento:.1f}% de preenchimento."
                    ),
                    coletor_id=coletor.id,
                    commit=False,
                    emitir=False,
                ))
        elif payload.nivel_preenchimento <= LIMIAR_NIVEL_CHEIO and coletor.status == "CHEIA":
            coletor.status = "OK"

        sensor.bateria = payload.bateria
        sensor.ultimo_ping = payload.timestamp or utc_now_naive()
        if payload.bateria < LIMIAR_BATERIA_BAIXA:
            ja_existe = (
                db.query(Notificacao)
                .filter(
                    Notificacao.sensor_id == sensor.id,
                    Notificacao.tipo == "bateria_baixa",
                    Notificacao.criada_em >= limite_tempo,
                )
                .first()
            )
            if not ja_existe:
                notificacoes.append(criar_notificacao(
                    db=db,
                    tipo="bateria_baixa",
                    titulo=f"Sensor #{sensor.id} - Bateria Baixa",
                    mensagem=(
                        f"O sensor do coletor em {coletor.localizacao} esta com "
                        f"{sensor.bateria:.1f}% de bateria."
                    ),
                    sensor_id=sensor.id,
                    coletor_id=coletor.id,
                    commit=False,
                    emitir=False,
                ))

        db.commit()

        # Dados derivados precisam refletir a leitura já no próximo GET/F5.
        cache = obter_cache()
        cache.invalidar("estatisticas")
        if coletor.parceiro_id is not None:
            cache.invalidar(f"estatisticas:{coletor.parceiro_id}")
        cache.invalidar("preview:estatisticas_resumo")
        cache.invalidar("preview:coletores_geojson")

        # Emitir somente depois do commit: o cliente nunca recebe estado ainda
        # não persistido e a telemetria passa a atualizar o dashboard em tempo real.
        try:
            from rotas.websocket import (
                emitir_atualizacao_coletor,
                emitir_atualizacao_sensor,
                emitir_nova_notificacao,
            )

            emissoes = [
                ("coletor", emitir_atualizacao_coletor, coletor_para_dict, coletor),
                ("sensor", emitir_atualizacao_sensor, sensor_para_dict, sensor),
                *[
                    ("notificacao", emitir_nova_notificacao, notificacao_para_dict, notificacao)
                    for notificacao in notificacoes
                ],
            ]
        except Exception as emit_error:
            logger.warning("Erro ao preparar emissoes da telemetria: %s", emit_error)
            emissoes = []

        for tipo_evento, emitir, serializar, objeto in emissoes:
            try:
                emitir(serializar(objeto))
            except Exception as emit_error:
                logger.warning(
                    "Erro ao emitir %s da telemetria via WebSocket: %s",
                    tipo_evento,
                    emit_error,
                )

        resposta = TelemetriaOut(
            mensagem="Telemetria registrada com sucesso",
            coletor_id=coletor.id,
            sensor_id=sensor.id,
            nivel_preenchimento=coletor.nivel_preenchimento,
            status_coletor=coletor.status,
            bateria=sensor.bateria,
            notificacoes_criadas=len(notificacoes),
        )
        return jsonify(resposta.model_dump(mode="json")), 200

    except Exception as e:
        db.rollback()
        logger.error("Erro em telemetria: %s", e)
        return tratar_erro_api(e)
    finally:
        db.close()
