"""
Serviço Comercial - Dashboard-TRONIK
====================================
Lógica de negócio para dashboard comercial e gestão de metas.
"""

from datetime import datetime, timedelta
from calendar import monthrange
import math
from sqlalchemy import extract, func
from banco_dados.modelos import (
    Coleta, MetaComercial, Coletor, Parceiro
)
from banco_dados.utils.datetime_utils import get_dias_uteis_mes
from banco_dados.utils.db_session import get_db_session
from banco_dados.services.relatorio_service import calcular_lucro_liquido_total
from banco_dados.serializers import coletor_para_dict, coleta_para_dict
import logging

logger = logging.getLogger(__name__)


class ComercialService:
    """Serviço para lógica de negócio comercial"""
    
    @staticmethod
    def get_ou_criar_meta_atual():
        """Retorna meta do mês atual ou cria uma nova"""
        db = get_db_session()
        try:
            hoje = datetime.now()
            mes = hoje.month
            ano = hoje.year
            
            meta = db.query(MetaComercial).filter_by(mes=mes, ano=ano).first()
            
            if not meta:
                meta = MetaComercial(
                    mes=mes,
                    ano=ano,
                    valor_meta=12000.00,  # Valor padrão baseado na análise
                    valor_realizado=0.0,
                    percentual_atingido=0.0,
                    status='em_andamento'
                )
                db.add(meta)
                db.commit()
                logger.info(f"Meta comercial criada para {mes}/{ano}")
            
            # Expurgar objeto da sessão para poder usá-lo depois
            db.expunge(meta)
            return meta
        finally:
            db.close()
    
    @staticmethod
    def calcular_faturamento_mes(mes=None, ano=None):
        """
        Calcula faturamento total do mês baseado em lucro líquido das coletas.
        
        Nota: Usa cálculo de lucro líquido (receita - custos de combustível)
        """
        db = get_db_session()
        try:
            hoje = datetime.now()
            mes = mes or hoje.month
            ano = ano or hoje.year
            
            # Buscar todas as coletas do mês
            coletas = db.query(Coleta).filter(
                extract('month', Coleta.data_hora) == mes,
                extract('year', Coleta.data_hora) == ano
            ).all()
            
            faturamento = 0.0
            for coleta in coletas:
                if coleta.volume_estimado and coleta.volume_estimado > 0:
                    lucro = calcular_lucro_liquido_total(
                        coleta.volume_estimado,
                        coleta.km_percorrido or 0.0,
                        coleta.preco_combustivel or 0.0
                    )
                    faturamento += lucro
            
            return float(faturamento)
        finally:
            db.close()
    
    @staticmethod
    def calcular_proximas_coletas(dias=7):
        """Retorna coletas agendadas nos próximos N dias"""
        db = get_db_session()
        try:
            from sqlalchemy.orm import joinedload
            hoje = datetime.now()
            fim = hoje + timedelta(days=dias)
            
            # Nota: Coletas futuras são identificadas por data_hora > hoje
            # Se não houver campo de agendamento, retornar coletas recentes como exemplo
            coletas = db.query(Coleta).options(
                joinedload(Coleta.coletor).joinedload(Coletor.parceiro),
                joinedload(Coleta.parceiro),
                joinedload(Coleta.tipo_coletor)
            ).filter(
                Coleta.data_hora >= hoje,
                Coleta.data_hora <= fim
            ).order_by(Coleta.data_hora).all()
            
            # Expurgar objetos da sessão
            for coleta in coletas:
                db.expunge(coleta)
            
            return coletas
        finally:
            db.close()
    
    @staticmethod
    def calcular_valor_agendado(coletas):
        """
        Calcula valor total estimado de coletas agendadas.
        Usa cálculo de lucro líquido.
        """
        valor_total = 0.0
        for coleta in coletas:
            if coleta.volume_estimado and coleta.volume_estimado > 0:
                lucro = calcular_lucro_liquido_total(
                    coleta.volume_estimado,
                    coleta.km_percorrido or 0.0,
                    coleta.preco_combustivel or 0.0
                )
                valor_total += lucro
        return valor_total
    
    @staticmethod
    def identificar_clientes_inativos(dias=30):
        """Identifica clientes sem coleta há N dias"""
        db = get_db_session()
        try:
            from sqlalchemy.orm import joinedload
            limite = datetime.now() - timedelta(days=dias)
            
            # Subquery: clientes com coletas recentes
            from sqlalchemy import select
            clientes_ativos_ids = db.query(Coletor.id).join(
                Coleta, Coleta.coletor_id == Coletor.id
            ).filter(
                Coleta.data_hora >= limite
            ).distinct().subquery()
            
            # Clientes sem coletas recentes (com eager loading)
            subquery = select(clientes_ativos_ids.c.id)
            clientes_inativos = db.query(Coletor).options(
                joinedload(Coletor.parceiro),
                joinedload(Coletor.tipo_material)
            ).filter(
                ~Coletor.id.in_(subquery)
            ).all()
            
            # Expurgar objetos da sessão
            for coletor in clientes_inativos:
                db.expunge(coletor)
            
            return clientes_inativos
        finally:
            db.close()
    
    @staticmethod
    def gerar_sugestoes_meta(falta, precos_servicos=None):
        """Gera sugestões de ações para atingir meta"""
        if precos_servicos is None:
            precos_servicos = {
                'coleta_0_40km': 800,
                'coleta_40_60km': 850,
                'palestra': 1000,
                'oficina': 800
            }
        
        if falta <= 0:
            return []
        
        sugestoes = []
        
        # Opção 1: Só coletas
        coletas_necessarias = math.ceil(falta / precos_servicos['coleta_0_40km'])
        sugestoes.append({
            'tipo': 'coletas',
            'quantidade': coletas_necessarias,
            'descricao': f"{coletas_necessarias} coletas (0-40km) de R$ {precos_servicos['coleta_0_40km']}"
        })
        
        # Opção 2: Só palestras
        palestras_necessarias = math.ceil(falta / precos_servicos['palestra'])
        sugestoes.append({
            'tipo': 'palestras',
            'quantidade': palestras_necessarias,
            'descricao': f"{palestras_necessarias} palestras de R$ {precos_servicos['palestra']}"
        })
        
        # Opção 3: Mix equilibrado
        coletas_mix = math.ceil(coletas_necessarias / 2)
        palestras_mix = math.ceil(palestras_necessarias / 2)
        valor_mix = (coletas_mix * precos_servicos['coleta_0_40km']) + (palestras_mix * precos_servicos['palestra'])
        
        sugestoes.append({
            'tipo': 'mix',
            'quantidade': coletas_mix + palestras_mix,
            'descricao': f"{coletas_mix} coletas + {palestras_mix} palestras (R$ {valor_mix:,.2f})"
        })
        
        return sugestoes
    
    @staticmethod
    def calcular_projecao_mes(faturamento_atual, dia_atual, dias_no_mes):
        """Projeta faturamento de fim de mês baseado no ritmo atual"""
        if dia_atual == 0:
            return faturamento_atual
        
        media_diaria = faturamento_atual / dia_atual
        projecao = media_diaria * dias_no_mes
        
        return projecao
    
    @staticmethod
    def atualizar_meta_atual():
        """Atualiza valores da meta do mês atual"""
        db = get_db_session()
        try:
            hoje = datetime.now()
            mes = hoje.month
            ano = hoje.year
            
            meta = db.query(MetaComercial).filter_by(mes=mes, ano=ano).first()
            if not meta:
                # Criar meta se não existir
                meta = MetaComercial(
                    mes=mes,
                    ano=ano,
                    valor_meta=12000.00,
                    valor_realizado=0.0,
                    percentual_atingido=0.0,
                    status='em_andamento'
                )
                db.add(meta)
                db.commit()
            
            faturamento = ComercialService.calcular_faturamento_mes()
            
            meta.valor_realizado = faturamento
            meta.percentual_atingido = (faturamento / meta.valor_meta * 100) if meta.valor_meta > 0 else 0
            
            # Atualizar status se mês acabou
            ultimo_dia = monthrange(hoje.year, hoje.month)[1]
            
            if hoje.day == ultimo_dia:
                meta.status = 'atingida' if meta.percentual_atingido >= 100 else 'nao_atingida'
            
            db.commit()
            
            # Fazer refresh para garantir que todos os dados estão carregados
            db.refresh(meta)
            
            # Expurgar objeto da sessão para poder usá-lo depois
            # Isso permite que o objeto seja usado fora da sessão
            db.expunge(meta)
            
            return meta
        finally:
            db.close()
    
    @staticmethod
    def calcular_metricas_financeiras_detalhadas(mes=None, ano=None):
        """Calcula métricas financeiras detalhadas do período"""
        db = get_db_session()
        try:
            hoje = datetime.now()
            mes = mes or hoje.month
            ano = ano or hoje.year
            
            coletas = db.query(Coleta).filter(
                extract('month', Coleta.data_hora) == mes,
                extract('year', Coleta.data_hora) == ano,
                Coleta.volume_estimado.isnot(None),
                Coleta.volume_estimado > 0
            ).all()
            
            if not coletas:
                return {
                    'lucro_medio_coleta': 0.0,
                    'custo_medio_km': 0.0,
                    'rentabilidade': 0.0,
                    'ticket_medio': 0.0,
                    'volume_medio_coleta': 0.0,
                    'receita_total': 0.0,
                    'custo_total': 0.0,
                    'lucro_total': 0.0,
                    'margem_lucro': 0.0,
                    'total_coletas': 0,
                    'total_km': 0.0,
                    'total_volume': 0.0
                }
            
            receita_total = 0.0
            custo_total = 0.0
            lucro_total = 0.0
            total_km = 0.0
            total_volume = 0.0
            
            for coleta in coletas:
                volume = coleta.volume_estimado or 0
                km = coleta.km_percorrido or 0
                preco_combustivel = coleta.preco_combustivel or 0
                
                # Receita bruta (R$ 1.00 por kg)
                receita = volume * 1.0
                
                # Custo de combustível
                if km > 0 and preco_combustivel > 0:
                    litros = km / 4.0  # 4 km por litro
                    custo = litros * preco_combustivel
                else:
                    custo = 0.0
                
                # Lucro líquido (usando função padronizada)
                lucro = calcular_lucro_liquido_total(volume, km, preco_combustivel)
                
                receita_total += receita
                custo_total += custo
                lucro_total += lucro
                total_km += km
                total_volume += volume
            
            num_coletas = len(coletas)
            
            return {
                'lucro_medio_coleta': lucro_total / num_coletas if num_coletas > 0 else 0.0,
                'custo_medio_km': custo_total / total_km if total_km > 0 else 0.0,
                'rentabilidade': (lucro_total / receita_total * 100) if receita_total > 0 else 0.0,
                'ticket_medio': receita_total / num_coletas if num_coletas > 0 else 0.0,
                'volume_medio_coleta': total_volume / num_coletas if num_coletas > 0 else 0.0,
                'receita_total': receita_total,
                'custo_total': custo_total,
                'lucro_total': lucro_total,
                'margem_lucro': (lucro_total / receita_total * 100) if receita_total > 0 else 0.0,
                'total_coletas': num_coletas,
                'total_km': total_km,
                'total_volume': total_volume,
                'eficiencia_kg_km': total_volume / total_km if total_km > 0 else 0.0
            }
        finally:
            db.close()
    
    @staticmethod
    def analisar_por_parceiro(mes=None, ano=None, meses_retroceder=None, todos_periodos=False):
        """
        Analisa métricas por parceiro
        
        Args:
            mes: Mês específico (1-12)
            ano: Ano específico
            meses_retroceder: Se fornecido, agrega dados dos últimos N meses a partir de mes/ano
            todos_periodos: Se True, inclui todas as coletas sem filtrar por data
        """
        db = get_db_session()
        try:
            hoje = datetime.now()
            
            from sqlalchemy.orm import joinedload
            from sqlalchemy import and_
            
            parceiros = db.query(Parceiro).options(
                joinedload(Parceiro.coletas)
            ).all()
            
            analise = []
            
            # Se todos_periodos=True, não filtrar por data
            if todos_periodos:
                data_inicio = None
                data_fim = None
            else:
                mes = mes or hoje.month
                ano = ano or hoje.year
                
                # Calcular período de data se meses_retroceder for fornecido
                if meses_retroceder and meses_retroceder > 1:
                    # Data fim: último dia do mês/ano especificado
                    if mes == 12:
                        data_fim = datetime(ano, 12, 31, 23, 59, 59)
                    else:
                        data_fim = datetime(ano, mes + 1, 1) - timedelta(seconds=1)
                    
                    # Data início: primeiro dia do mês retrocedido (meses_retroceder meses atrás)
                    # Exemplo: se mes=11, ano=2025, meses_retroceder=6
                    # data_inicio deve ser 01/06/2025 (6 meses antes de novembro)
                    mes_inicio = mes - (meses_retroceder - 1)
                    ano_inicio = ano
                    while mes_inicio <= 0:
                        mes_inicio += 12
                        ano_inicio -= 1
                    data_inicio = datetime(ano_inicio, mes_inicio, 1)
                else:
                    # Apenas mês/ano específico
                    data_inicio = datetime(ano, mes, 1)
                    if mes == 12:
                        data_fim = datetime(ano, 12, 31, 23, 59, 59)
                    else:
                        data_fim = datetime(ano, mes + 1, 1) - timedelta(seconds=1)
            
            for parceiro in parceiros:
                # Filtrar coletas pelo período calculado (ou todas se todos_periodos=True)
                if todos_periodos:
                    coletas_parceiro = [
                        c for c in parceiro.coletas
                        if c.volume_estimado and c.volume_estimado > 0
                    ]
                else:
                    coletas_parceiro = [
                        c for c in parceiro.coletas
                        if data_inicio <= c.data_hora <= data_fim
                        and c.volume_estimado and c.volume_estimado > 0
                    ]
                
                # Incluir todos os parceiros, mesmo sem coletas no período
                # (mostrar valores zerados)
                receita = sum(c.volume_estimado * 1.0 for c in coletas_parceiro) if coletas_parceiro else 0.0
                custo = sum(
                    ((c.km_percorrido or 0) / 4.0) * (c.preco_combustivel or 0)
                    for c in coletas_parceiro
                ) if coletas_parceiro else 0.0
                # Lucro usando função padronizada (soma de todos os lucros individuais)
                lucro = sum(
                    calcular_lucro_liquido_total(
                        c.volume_estimado or 0,
                        c.km_percorrido or 0,
                        c.preco_combustivel or 0
                    )
                    for c in coletas_parceiro
                ) if coletas_parceiro else 0.0
                volume = sum(c.volume_estimado for c in coletas_parceiro) if coletas_parceiro else 0.0
                km = sum(c.km_percorrido or 0 for c in coletas_parceiro) if coletas_parceiro else 0.0
                
                analise.append({
                    'parceiro_id': parceiro.id,
                    'parceiro_nome': parceiro.nome,
                    'num_coletas': len(coletas_parceiro),
                    'volume_total': float(volume),
                    'receita_total': float(receita),
                    'custo_total': float(custo),
                    'lucro_total': float(lucro),
                    'lucro_medio_coleta': float(lucro / len(coletas_parceiro)) if coletas_parceiro else 0.0,
                    'km_total': float(km),
                    'eficiencia_kg_km': float(volume / km) if km > 0 else 0.0,
                    'margem_lucro': float((lucro / receita * 100) if receita > 0 else 0.0)
                })
            
            # Ordenar: primeiro por número de coletas (decrescente), depois por lucro total (decrescente), depois por nome
            analise.sort(key=lambda x: (x['num_coletas'], x['lucro_total'], x['parceiro_nome']), reverse=True)
            
            # Expurgar objetos
            for parceiro in parceiros:
                db.expunge(parceiro)
            
            return analise
        finally:
            db.close()
    
    @staticmethod
    def comparar_com_mes_anterior():
        """Compara métricas do mês atual com mês anterior"""
        hoje = datetime.now()
        mes_atual = hoje.month
        ano_atual = hoje.year
        
        # Calcular mês anterior
        if mes_atual == 1:
            mes_anterior = 12
            ano_anterior = ano_atual - 1
        else:
            mes_anterior = mes_atual - 1
            ano_anterior = ano_atual
        
        # Métricas do mês atual
        metricas_atual = ComercialService.calcular_metricas_financeiras_detalhadas(mes_atual, ano_atual)
        faturamento_atual = ComercialService.calcular_faturamento_mes(mes_atual, ano_atual)
        
        # Métricas do mês anterior
        metricas_anterior = ComercialService.calcular_metricas_financeiras_detalhadas(mes_anterior, ano_anterior)
        faturamento_anterior = ComercialService.calcular_faturamento_mes(mes_anterior, ano_anterior)
        
        # Calcular variações
        def calcular_variacao(atual, anterior):
            if anterior == 0:
                return 0.0 if atual == 0 else 100.0
            return ((atual - anterior) / anterior) * 100
        
        return {
            'mes_atual': {
                'mes': mes_atual,
                'ano': ano_atual,
                'faturamento': faturamento_atual,
                'metricas': metricas_atual
            },
            'mes_anterior': {
                'mes': mes_anterior,
                'ano': ano_anterior,
                'faturamento': faturamento_anterior,
                'metricas': metricas_anterior
            },
            'variacoes': {
                'faturamento': calcular_variacao(faturamento_atual, faturamento_anterior),
                'lucro_total': calcular_variacao(metricas_atual['lucro_total'], metricas_anterior['lucro_total']),
                'num_coletas': calcular_variacao(metricas_atual['total_coletas'], metricas_anterior['total_coletas']),
                'volume_total': calcular_variacao(metricas_atual['total_volume'], metricas_anterior['total_volume']),
                'ticket_medio': calcular_variacao(metricas_atual['ticket_medio'], metricas_anterior['ticket_medio'])
            }
        }
    
    @staticmethod
    def get_lucro_por_parceiro(mes=None, ano=None, meses_retroceder=None, todos_periodos=False):
        """Retorna lucro por parceiro para gráfico"""
        analise = ComercialService.analisar_por_parceiro(mes, ano, meses_retroceder, todos_periodos)
        return [
            {
                'parceiro_id': item['parceiro_id'],
                'parceiro': item['parceiro_nome'],
                'parceiro_nome': item['parceiro_nome'],
                'lucro': item['lucro_total'],
                'lucro_total': item['lucro_total'],
                'receita': item['receita_total'],
                'receita_total': item['receita_total'],
                'custo': item['custo_total'],
                'custo_total': item['custo_total']
            }
            for item in analise[:10]  # Top 10
        ]
    
    @staticmethod
    def get_dashboard_data(mes=None, ano=None, meses_retroceder=None, todos_periodos=False):
        """Retorna todos os dados para o dashboard comercial"""
        hoje = datetime.now()
        # Se todos_periodos=True, não usar mes/ano específico
        if todos_periodos:
            mes_atual = hoje.month  # Usar mês atual apenas para meta (se necessário)
            ano_atual = hoje.year
        else:
            mes_atual = mes or hoje.month
            ano_atual = ano or hoje.year
        dias_no_mes = monthrange(ano_atual, mes_atual)[1]
        dia_atual = hoje.day if mes_atual == hoje.month and ano_atual == hoje.year else dias_no_mes
        
        # Meta
        if mes_atual == hoje.month and ano_atual == hoje.year:
            meta = ComercialService.get_ou_criar_meta_atual()
        else:
            db = get_db_session()
            try:
                meta = db.query(MetaComercial).filter_by(mes=mes_atual, ano=ano_atual).first()
                if not meta:
                    # Criar meta temporária para histórico
                    meta = MetaComercial(
                        mes=mes_atual,
                        ano=ano_atual,
                        valor_meta=12000.00,
                        valor_realizado=0.0,
                        percentual_atingido=0.0,
                        status='em_andamento'
                    )
                    db.add(meta)
                    db.commit()
                db.refresh(meta)
                db.expunge(meta)
            finally:
                db.close()
        
        # Faturamento
        faturamento_atual = ComercialService.calcular_faturamento_mes(mes_atual, ano_atual)
        percentual_meta = (faturamento_atual / meta.valor_meta * 100) if meta.valor_meta > 0 else 0
        falta_para_meta = max(0, meta.valor_meta - faturamento_atual)
        
        # Próximas coletas (apenas para mês atual)
        if mes_atual == hoje.month and ano_atual == hoje.year:
            proximas = ComercialService.calcular_proximas_coletas(dias=7)
            valor_agendado = ComercialService.calcular_valor_agendado(proximas)
        else:
            proximas = []
            valor_agendado = 0.0
        
        # Clientes inativos (apenas para mês atual)
        if mes_atual == hoje.month and ano_atual == hoje.year:
            clientes_inativos = ComercialService.identificar_clientes_inativos(dias=30)
        else:
            clientes_inativos = []
        
        # Sugestões (apenas para mês atual)
        if mes_atual == hoje.month and ano_atual == hoje.year:
            sugestoes = ComercialService.gerar_sugestoes_meta(falta_para_meta)
        else:
            sugestoes = []
        
        # Projeção (apenas para mês atual)
        if mes_atual == hoje.month and ano_atual == hoje.year:
            projecao_fim_mes = ComercialService.calcular_projecao_mes(
                faturamento_atual, 
                dia_atual, 
                dias_no_mes
            )
        else:
            projecao_fim_mes = faturamento_atual
        
        # Dias úteis restantes (apenas para mês atual)
        if mes_atual == hoje.month and ano_atual == hoje.year:
            dias_uteis_totais = get_dias_uteis_mes(ano_atual, mes_atual)
            dias_uteis_decorridos = sum(
                1 for dia in range(1, dia_atual + 1)
                if datetime(ano_atual, mes_atual, dia).weekday() < 5
            )
            dias_uteis_restantes = dias_uteis_totais - dias_uteis_decorridos
        else:
            dias_uteis_restantes = 0
        
        # Métricas financeiras detalhadas
        metricas = ComercialService.calcular_metricas_financeiras_detalhadas(mes_atual, ano_atual)
        
        # Análise por parceiro (com suporte a período agregado ou todos os períodos)
        analise_parceiros = ComercialService.analisar_por_parceiro(mes_atual, ano_atual, meses_retroceder, todos_periodos)
        
        # Lucro por parceiro (para gráfico)
        lucro_parceiros = ComercialService.get_lucro_por_parceiro(mes_atual, ano_atual, meses_retroceder, todos_periodos)
        
        return {
            'meta': meta.to_dict() if meta else {},
            'faturamento_atual': faturamento_atual,
            'percentual_meta': percentual_meta,
            'falta_para_meta': falta_para_meta,
            'proximas_coletas': [coleta_para_dict(c) for c in proximas],
            'valor_agendado_semana': valor_agendado,
            'clientes_inativos': {
                'quantidade': len(clientes_inativos),
                'lista': [coletor_para_dict(c) for c in clientes_inativos[:5]]  # Primeiros 5
            },
            'sugestoes': sugestoes,
            'projecao_fim_mes': projecao_fim_mes,
            'dias_restantes_mes': dias_no_mes - dia_atual,
            'dias_uteis_restantes': dias_uteis_restantes,
            'dia_atual': dia_atual,
            'dias_no_mes': dias_no_mes,
            'metricas_financeiras': metricas,
            'analise_parceiros': analise_parceiros,
            'lucro_por_parceiro': lucro_parceiros,
            'periodo': {
                'mes': mes_atual,
                'ano': ano_atual
            }
        }

