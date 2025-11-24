"""
Rotas de Relatórios - Dashboard-TRONIK
=======================================
Endpoints para relatórios financeiros e operacionais.
"""

from flask import Blueprint, jsonify, request, Response
from flask_login import login_required
from rotas.api.decorators import get_db
from banco_dados.services.relatorio_service import gerar_relatorio
from banco_dados.utils.erros import tratar_erro_api
from banco_dados.utils.logger import obter_logger
from datetime import datetime
from io import BytesIO

logger = obter_logger(__name__)

# Criar blueprint
relatorios_bp = Blueprint('relatorios', __name__)


@relatorios_bp.route('/relatorios', methods=['GET'])
def obter_relatorios():
    """Endpoint para obter dados para relatórios com dados financeiros e paginação"""
    db = get_db()
    try:
        # Obter parâmetros de filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        parceiro_id = request.args.get('parceiro_id', type=int)
        tipo_operacao = request.args.get('tipo_operacao')
        
        # Parâmetros de paginação com validação
        pagina = request.args.get('pagina', type=int, default=1)
        if pagina < 1:
            pagina = 1
        if pagina > 1000:  # Limite máximo de páginas
            pagina = 1000
        
        por_pagina = request.args.get('por_pagina', type=int, default=50)
        if por_pagina < 1:
            por_pagina = 1
        if por_pagina > 500:  # Limite máximo de itens por página
            por_pagina = 500
        
        # Gerar relatório usando serviço
        relatorio = gerar_relatorio(
            db,
            data_inicio=data_inicio,
            data_fim=data_fim,
            parceiro_id=parceiro_id,
            tipo_operacao=tipo_operacao,
            pagina=pagina,
            por_pagina=por_pagina
        )
        
        return jsonify(relatorio)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@relatorios_bp.route('/relatorios/exportar-pdf', methods=['GET'])
@login_required
def exportar_relatorio_pdf():
    """Endpoint para exportar relatório em PDF"""
    db = get_db()
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from banco_dados.services.relatorio_service import gerar_relatorio
        
        # Obter parâmetros de filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        parceiro_id = request.args.get('parceiro_id', type=int)
        tipo_operacao = request.args.get('tipo_operacao')
        
        # Gerar relatório (sem paginação para PDF)
        relatorio = gerar_relatorio(
            db,
            data_inicio=data_inicio,
            data_fim=data_fim,
            parceiro_id=parceiro_id,
            tipo_operacao=tipo_operacao,
            pagina=1,
            por_pagina=50  # Limitar a 50 para PDF
        )
        
        resumo = relatorio['resumo']
        detalhes = relatorio['detalhes']
        
        # Criar PDF em memória
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#27ae60'),
            spaceAfter=12,
            alignment=1  # Center
        )
        
        # Conteúdo do PDF
        story = []
        
        # Título
        story.append(Paragraph("Relatório de Coletas - TRONIK Recicla", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Período
        periodo_text = f"Período: {data_inicio or 'Início'} a {data_fim or 'Fim'}"
        story.append(Paragraph(periodo_text, styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        
        # Resumo
        resumo_data = [
            ['Métrica', 'Valor'],
            ['Total de Coletas', str(resumo['total_coletas'])],
            ['Volume Total (kg)', f'{resumo["volume_total"]:.2f}'],
            ['KM Total', f'{resumo["km_total"]:.2f}'],
            ['Custo Combustível', f'R$ {resumo["custo_combustivel_total"]:.2f}'],
            ['Lucro Total', f'R$ {resumo["lucro_total"]:.2f}'],
        ]
        
        resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        story.append(Paragraph("<b>Resumo</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        story.append(resumo_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Detalhamento
        if detalhes:
            story.append(Paragraph("<b>Detalhamento de Coletas</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            detalhes_data = [['Data', 'Coletor', 'Volume (kg)', 'KM', 'Lucro (R$)']]
            
            for coleta in detalhes[:50]:
                data_str = coleta.get('data_hora', 'N/A')
                if data_str and data_str != 'N/A':
                    try:
                        dt = datetime.fromisoformat(data_str.replace('Z', '+00:00'))
                        data_str = dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        pass
                
                lixeira_nome = coleta.get('coletor', {}).get('localizacao', 'N/A')[:30]
                volume = f'{coleta.get("volume_estimado", 0):.2f}'
                km = f'{coleta.get("km_percorrido", 0):.2f}'
                # Calcular lucro líquido (bruto R$ 1,00 - custos de combustível)
                from banco_dados.services.relatorio_service import calcular_lucro_liquido_total
                volume = coleta.get("volume_estimado", 0) or 0
                km = coleta.get("km_percorrido", 0) or 0
                preco = coleta.get("preco_combustivel", 0) or 0
                lucro = f'{calcular_lucro_liquido_total(volume, km, preco):.2f}'
                
                detalhes_data.append([data_str, lixeira_nome, volume, km, lucro])
            
            if len(detalhes) > 50:
                detalhes_data.append(['...', f'({len(detalhes) - 50} coletas adicionais)', '', '', ''])
            
            detalhes_table = Table(detalhes_data, colWidths=[1.2*inch, 2*inch, 1*inch, 0.8*inch, 1*inch])
            detalhes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            
            story.append(detalhes_table)
        
        # Gerar PDF
        doc.build(story)
        
        # Retornar PDF
        buffer.seek(0)
        filename = f'relatorio_tronik_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        return tratar_erro_api(e)
    finally:
        db.close()

