#!/bin/bash
# Script de Migração: Render → Railway
# =====================================
# Este script facilita a migração do banco de dados do Render para Railway

set -e  # Parar em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Migração Render → Railway${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verificar argumentos
if [ $# -lt 2 ]; then
    echo -e "${RED}Erro: Argumentos insuficientes${NC}"
    echo ""
    echo "Uso:"
    echo "  ./migrar_para_railway.sh <DATABASE_URL_RENDER> <DATABASE_URL_RAILWAY> [backup_file]"
    echo ""
    echo "Exemplo:"
    echo "  ./migrar_para_railway.sh \\"
    echo "    'postgresql://user:pass@render-host/db' \\"
    echo "    'postgresql://user:pass@railway-host/db'"
    echo ""
    exit 1
fi

RENDER_DB_URL=$1
RAILWAY_DB_URL=$2
BACKUP_FILE=${3:-"backup_render_$(date +%Y%m%d_%H%M%S).sql"}

echo -e "${YELLOW}Configuração:${NC}"
echo "  Render DB: ${RENDER_DB_URL:0:30}..."
echo "  Railway DB: ${RAILWAY_DB_URL:0:30}..."
echo "  Backup: $BACKUP_FILE"
echo ""

# Verificar se pg_dump está instalado
if ! command -v pg_dump &> /dev/null; then
    echo -e "${RED}Erro: pg_dump não encontrado${NC}"
    echo "Instale PostgreSQL client tools:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "  macOS: brew install postgresql"
    exit 1
fi

# Verificar se psql está instalado
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Erro: psql não encontrado${NC}"
    echo "Instale PostgreSQL client tools:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "  macOS: brew install postgresql"
    exit 1
fi

# Passo 1: Backup do Render
echo -e "${YELLOW}[1/3] Fazendo backup do banco Render...${NC}"
# Usar pg_dump com flag de compatibilidade para versões mais novas
if pg_dump "$RENDER_DB_URL" > "$BACKUP_FILE" 2>&1; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✓ Backup criado: $BACKUP_FILE (${BACKUP_SIZE})${NC}"
else
    echo -e "${RED}✗ Erro ao criar backup${NC}"
    exit 1
fi
echo ""

# Passo 2: Verificar conexão Railway
echo -e "${YELLOW}[2/3] Verificando conexão com Railway...${NC}"
if psql "$RAILWAY_DB_URL" -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Conexão com Railway OK${NC}"
else
    echo -e "${RED}✗ Erro ao conectar no Railway${NC}"
    echo "Verifique se a DATABASE_URL está correta"
    exit 1
fi
echo ""

# Passo 3: Importar no Railway
echo -e "${YELLOW}[3/3] Importando dados para Railway...${NC}"
echo -e "${YELLOW}⚠️  ATENÇÃO: Isso irá sobrescrever dados existentes no Railway!${NC}"
read -p "Continuar? (s/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Migração cancelada."
    exit 0
fi

if psql "$RAILWAY_DB_URL" < "$BACKUP_FILE"; then
    echo -e "${GREEN}✓ Dados importados com sucesso${NC}"
else
    echo -e "${RED}✗ Erro ao importar dados${NC}"
    exit 1
fi
echo ""

# Passo 4: Verificar migração
echo -e "${YELLOW}[4/4] Verificando migração...${NC}"
echo "Contando registros nas principais tabelas:"
psql "$RAILWAY_DB_URL" -c "
SELECT 
    'usuarios' as tabela, COUNT(*) as registros FROM usuarios
UNION ALL
SELECT 'coletores', COUNT(*) FROM coletores
UNION ALL
SELECT 'coletas', COUNT(*) FROM coletas
UNION ALL
SELECT 'sensores', COUNT(*) FROM sensores;
" 2>/dev/null || echo "Algumas tabelas podem não existir ainda (normal se banco novo)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Migração concluída com sucesso!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Próximos passos:"
echo "  1. Configure DATABASE_URL no Railway (já deve estar configurada)"
echo "  2. Faça deploy da aplicação no Railway"
echo "  3. Teste todas as funcionalidades"
echo "  4. Mantenha o backup: $BACKUP_FILE"
echo ""


