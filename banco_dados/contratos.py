"""
Contratos de API - Dashboard-TRONIK
====================================

Schemas Pydantic v2 que validam a *entrada* e documentam a *saida* dos
endpoints HTTP. Todos os payloads que chegam do ESP32, do CRM ou do
frontend passam por um schema aqui antes de virar chamada de ORM.

Filosofia
---------
1. Contratos explicitos: cada endpoint critico tem um `*In` (entrada) e
   opcionalmente um `*Out` (resposta). Nunca confiar em `request.get_json()`
   "cru" em endpoints que afetam estado.
2. Firmware-friendly: `TelemetriaIn` usa `model_config = ConfigDict(extra='ignore')`
   para que versoes futuras do ESP32 possam adicionar campos sem quebrar
   a API. Fields sensiveis sao obrigatorios.
3. Erros traduzidos: `ValidationError` do Pydantic e convertido em
   `ErroValidacao` via `parse_ou_erro`, que respeita o envelope de erros
   do resto da API (`{"erro": ..., "detalhes": ...}`).
4. Zero acoplamento com SQLAlchemy: schemas sao puro dado. Serializacao
   de modelos ORM continua em `banco_dados.serializers`.

Uso tipico no endpoint:

    from banco_dados.contratos import TelemetriaIn, parse_ou_erro

    @sensores_bp.route('/sensor/telemetria', methods=['POST'])
    def receber_telemetria():
        payload = parse_ou_erro(TelemetriaIn, request.get_json(silent=True))
        # payload.sensor_id, payload.nivel_preenchimento, ... sao validados
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from banco_dados.utils.erros import ErroValidacao

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Entrada de telemetria (ESP32 -> POST /api/sensor/telemetria)
# ---------------------------------------------------------------------------
class TelemetriaIn(BaseModel):
    """Payload enviado pelo firmware do ESP32 a cada leitura.

    - `nivel_preenchimento` e `bateria` sao porcentagens 0-100.
    - `leituras_tof` e opcional (lista crua do ToF, para debug / media).
    - `api_key`: validado em ``rotas.api.sensores.receber_telemetria`` contra
      ``Sensor.api_token`` ou ``TELEMETRY_SHARED_SECRET`` (ver ``telemetria_auth``).
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    sensor_id: int = Field(..., ge=1, description="ID do Sensor no DB")
    coletor_id: int = Field(..., ge=1, description="ID do Coletor associado")
    nivel_preenchimento: float = Field(..., ge=0, le=100, description="% preenchimento (0-100)")
    bateria: float = Field(..., ge=0, le=100, description="% bateria (0-100)")
    leituras_tof: Optional[list[float]] = Field(
        default=None,
        description="Leituras cruas do ToF (cm) para debug; ignoradas pelo server",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Token do device (Sensor.api_token ou secret global TELEMETRY_SHARED_SECRET)",
    )
    firmware_version: Optional[str] = Field(default=None, max_length=32)
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Momento da leitura no device; server usa utc_now se ausente",
    )


class TelemetriaOut(BaseModel):
    """Resposta do endpoint de telemetria."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="ok")
    mensagem: str
    coletor_id: int
    sensor_id: int
    nivel_preenchimento: float
    status_coletor: str
    bateria: float
    notificacoes_criadas: int = 0


# ---------------------------------------------------------------------------
# Schemas de saida (espelham serializers.py mas tipados)
# ---------------------------------------------------------------------------
class ParceiroResumo(BaseModel):
    id: int
    nome: str


class TipoResumo(BaseModel):
    id: int
    nome: str


class ColetorOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    localizacao: str
    nivel_preenchimento: Optional[float] = None
    status: Optional[str] = None
    ultima_coleta: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    parceiro: Optional[ParceiroResumo] = None
    tipo_material: Optional[TipoResumo] = None


class SensorOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    coletor_id: int
    bateria: Optional[float] = None
    ultimo_ping: Optional[datetime] = None
    tipo_sensor: Optional[TipoResumo] = None


# ---------------------------------------------------------------------------
# Entrada: criacao/atualizacao de coletor e coleta
# ---------------------------------------------------------------------------
class CriarColetorIn(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    localizacao: str = Field(..., min_length=1, max_length=150)
    nivel_preenchimento: Optional[float] = Field(default=0.0, ge=0, le=100)
    status: Optional[str] = Field(default="OK", max_length=20)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    parceiro_id: Optional[int] = Field(default=None, ge=1)
    tipo_material_id: Optional[int] = Field(default=None, ge=1)


class AtualizarColetorIn(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    localizacao: Optional[str] = Field(default=None, min_length=1, max_length=150)
    nivel_preenchimento: Optional[float] = Field(default=None, ge=0, le=100)
    status: Optional[str] = Field(default=None, max_length=20)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    parceiro_id: Optional[int] = Field(default=None, ge=1)
    tipo_material_id: Optional[int] = Field(default=None, ge=1)


class CriarSensorIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    coletor_id: int = Field(..., ge=1)
    tipo_sensor_id: Optional[int] = Field(default=None, ge=1)
    bateria: Optional[float] = Field(default=100.0, ge=0, le=100)


class CriarColetaIn(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    coletor_id: int = Field(..., ge=1)
    data_hora: Optional[datetime] = None
    volume_estimado: Optional[float] = Field(default=None, ge=0)
    tipo_operacao: Optional[str] = Field(default=None, max_length=50)
    km_percorrido: Optional[float] = Field(default=None, ge=0)
    preco_combustivel: Optional[float] = Field(default=None, ge=0)
    lucro_por_kg: Optional[float] = Field(default=None)
    emissao_mtr: bool = False
    tipo_coletor_id: Optional[int] = Field(default=None, ge=1)
    parceiro_id: Optional[int] = Field(default=None, ge=1)

    @field_validator("tipo_operacao")
    @classmethod
    def tipo_operacao_permitido(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        permitidos = {"Avulsa", "Campanha"}
        if v not in permitidos:
            raise ValueError(f"tipo_operacao deve ser um de {sorted(permitidos)}")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_ou_erro(schema: Type[T], payload: Any) -> T:
    """Valida `payload` contra `schema` ou levanta `ErroValidacao`.

    Traduz `pydantic.ValidationError` em erro 400 com `detalhes` legiveis,
    preservando o formato de resposta padronizado de erros da API.
    """
    if payload is None:
        raise ErroValidacao("Payload JSON nao fornecido ou invalido")
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        detalhes = [
            {
                "campo": ".".join(str(p) for p in err["loc"]),
                "mensagem": err["msg"],
                "tipo": err["type"],
            }
            for err in exc.errors()
        ]
        raise ErroValidacao("Erros de validacao no payload", {"detalhes": detalhes}) from exc
