"""
Testes de Estatísticas e Relatórios - Dashboard-TRONIK
======================================================
Testa endpoints de estatísticas e relatórios.
"""

import pytest
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from banco_dados.modelos import Lixeira, Coleta, Parceiro, TipoMaterial, TipoColetor
from banco_dados.utils import utc_now_naive


class TestEstatisticas:
    """Testes do endpoint de estatísticas"""
    
    def test_obter_estatisticas_empty(self, client, db_session):
        """Testa obter estatísticas quando não há dados"""
        response = client.get('/api/estatisticas')
        assert response.status_code == 200
        data = response.get_json()
        assert 'total_lixeiras' in data
        assert 'lixeiras_alerta' in data
        assert 'nivel_medio' in data
        assert 'coletas_hoje' in data
        assert data['total_lixeiras'] == 0
        assert data['coletas_hoje'] == 0
    
    def test_obter_estatisticas_with_data(self, client, db_session):
        """Testa obter estatísticas com dados"""
        # Criar lixeiras e coletas
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Stats')
        db_session.add(parceiro)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        # Criar 2 lixeiras
        lixeira1 = Lixeira(
            localizacao='Lixeira 1',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira1)
        db_session.flush()
        
        lixeira2 = Lixeira(
            localizacao='Lixeira 2',
            nivel_preenchimento=85.0,  # > 80 para ser contada como alerta
            status='ALERTA',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira2)
        db_session.flush()
        
        # Criar 3 coletas
        for i in range(3):
            coleta = Coleta(
                lixeira_id=lixeira1.id if i % 2 == 0 else lixeira2.id,
                data_hora=utc_now_naive(),
                volume_estimado=100.0 + i * 10,
                tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
                parceiro_id=parceiro.id
            )
            db_session.add(coleta)
        
        db_session.commit()
        
        # Obter estatísticas
        response = client.get('/api/estatisticas')
        assert response.status_code == 200
        data = response.get_json()
        assert data['total_lixeiras'] == 2
        assert 'coletas_hoje' in data
        assert 'nivel_medio' in data
        assert 'lixeiras_alerta' in data
        assert data['lixeiras_alerta'] >= 1  # Pelo menos a lixeira 2 com 80%


class TestRelatorios:
    """Testes do endpoint de relatórios"""
    
    def test_obter_relatorios_empty(self, client, db_session):
        """Testa obter relatórios quando não há coletas"""
        response = client.get('/api/relatorios')
        assert response.status_code == 200
        data = response.get_json()
        assert 'resumo' in data
        assert 'detalhes' in data
        assert data['resumo']['total_coletas'] == 0
        assert data['resumo']['volume_total'] == 0.0
    
    def test_obter_relatorios_with_data(self, client, db_session):
        """Testa obter relatórios com dados"""
        # Criar lixeira e coletas
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Relatórios')
        db_session.add(parceiro)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        lixeira = Lixeira(
            localizacao='Lixeira Relatórios',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        # Criar coletas com dados financeiros
        coleta1 = Coleta(
            lixeira_id=lixeira.id,
            data_hora=utc_now_naive(),
            volume_estimado=100.0,
            tipo_operacao='Avulsa',
            km_percorrido=10.0,
            preco_combustivel=5.50,
            lucro_por_kg=2.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
            parceiro_id=parceiro.id
        )
        db_session.add(coleta1)
        
        coleta2 = Coleta(
            lixeira_id=lixeira.id,
            data_hora=utc_now_naive(),
            volume_estimado=200.0,
            tipo_operacao='Campanha',
            km_percorrido=20.0,
            preco_combustivel=5.50,
            lucro_por_kg=2.5,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
            parceiro_id=parceiro.id
        )
        db_session.add(coleta2)
        db_session.commit()
        
        # Obter relatórios
        response = client.get('/api/relatorios')
        assert response.status_code == 200
        data = response.get_json()
        assert 'resumo' in data
        resumo = data['resumo']
        assert resumo['total_coletas'] == 2
        assert resumo['volume_total'] == 300.0
        assert resumo['km_total'] == 30.0
        assert 'custo_combustivel_total' in resumo
        assert 'lucro_total' in resumo
        assert 'coletas_por_lixeira' in resumo
    
    def test_obter_relatorios_filter_by_date(self, client, db_session):
        """Testa filtrar relatórios por data"""
        # Criar lixeira
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Filtro')
        db_session.add(parceiro)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        lixeira = Lixeira(
            localizacao='Lixeira Filtro',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        # Criar coleta com data específica
        data_especifica = datetime(2025, 11, 20, 10, 0, 0)
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=data_especifica,
            volume_estimado=100.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
            parceiro_id=parceiro.id
        )
        db_session.add(coleta)
        db_session.commit()
        
        # Filtrar por data
        response = client.get('/api/relatorios?data_inicio=2025-11-20&data_fim=2025-11-20')
        assert response.status_code == 200
        data = response.get_json()
        assert 'resumo' in data
        assert data['resumo']['total_coletas'] >= 1
    
    def test_obter_relatorios_calculo_combustivel(self, client, db_session):
        """Testa cálculo correto de custo de combustível"""
        # Criar lixeira e coleta
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Combustível')
        db_session.add(parceiro)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        lixeira = Lixeira(
            localizacao='Lixeira Combustível',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        # Criar coleta: 10 km, R$ 5.50/L, consumo 4 km/L
        # Custo esperado: (10 / 4) * 5.50 = 2.5 * 5.50 = 13.75
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=utc_now_naive(),
            volume_estimado=100.0,
            km_percorrido=10.0,
            preco_combustivel=5.50,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
            parceiro_id=parceiro.id
        )
        db_session.add(coleta)
        db_session.commit()
        
        # Obter relatórios
        response = client.get('/api/relatorios')
        assert response.status_code == 200
        data = response.get_json()
        assert 'resumo' in data
        resumo = data['resumo']
        assert 'custo_combustivel_total' in resumo
        # Verificar cálculo: (10 / 4) * 5.50 = 13.75
        assert abs(resumo['custo_combustivel_total'] - 13.75) < 0.01
    
    def test_obter_relatorios_calculo_lucro(self, client, db_session):
        """Testa cálculo correto de lucro total"""
        # Criar lixeira e coleta
        tipo_material = db_session.query(TipoMaterial).first()
        parceiro = Parceiro(nome='Parceiro Lucro')
        db_session.add(parceiro)
        db_session.flush()
        
        tipo_coletor = db_session.query(TipoColetor).first()
        
        lixeira = Lixeira(
            localizacao='Lixeira Lucro',
            nivel_preenchimento=50.0,
            status='OK',
            parceiro_id=parceiro.id,
            tipo_material_id=tipo_material.id if tipo_material else None
        )
        db_session.add(lixeira)
        db_session.flush()
        
        # Criar coleta: 100 kg, R$ 2.00/kg
        # Lucro esperado: 100 * 2.00 = 200.00
        coleta = Coleta(
            lixeira_id=lixeira.id,
            data_hora=utc_now_naive(),
            volume_estimado=100.0,
            lucro_por_kg=2.0,
            tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
            parceiro_id=parceiro.id
        )
        db_session.add(coleta)
        db_session.commit()
        
        # Obter relatórios
        response = client.get('/api/relatorios')
        assert response.status_code == 200
        data = response.get_json()
        assert 'resumo' in data
        resumo = data['resumo']
        assert 'lucro_total' in resumo
        # Verificar cálculo: 100 * 2.00 = 200.00
        assert abs(resumo['lucro_total'] - 200.0) < 0.01

