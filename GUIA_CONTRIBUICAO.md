# Guia de Contribuição - Dashboard-TRONIK

## Como Contribuir

Este guia explica como cada membro da equipe deve contribuir para o projeto.

## Áreas de Desenvolvimento

A equipe deve se auto-organizar baseada nos interesses e habilidades de cada membro. O projeto permite diferentes abordagens:

### Frontend
**Foco:** Interface do usuário
- HTML, CSS, JavaScript
- Responsividade e UX
- Integração com APIs

**Arquivos principais:**
- `templates/` - Páginas HTML
- `estatico/css/` - Estilos
- `estatico/js/` - JavaScript
- `estatico/imagens/` - Assets

### Backend
**Foco:** Lógica e APIs
- Flask e APIs REST
- Banco de dados SQLite
- Processamento de dados

**Arquivos principais:**
- `app.py` - Aplicação principal
- `rotas/` - Endpoints da API
- `banco_dados/` - Modelos e configuração

### Dados e Testes
**Foco:** Qualidade e validação
- Dados mock e cenários
- Testes automatizados
- Validação de dados

**Arquivos principais:**
- `dados/` - Dados mock
- Testes automatizados

### Documentação
**Foco:** Organização e clareza
- Manutenção da documentação
- Comentários no código
- Guias de uso

**Arquivos principais:**
- `README.md`
- Comentários inline
- Guias específicos

## Fluxo de Trabalho

### 1. Setup Inicial
```bash
# Clone o repositório
git clone [URL_DO_REPOSITORIO]
cd Dashboard-TRONIK

# Crie uma branch para sua área
git checkout -b frontend/interface-principal
git checkout -b backend/api-endpoints
git checkout -b dados/mock-expansion
git checkout -b docs/readme-update
```

### 2. Desenvolvimento
1. **Leia os comentários TODO** nos arquivos
2. **Implemente uma funcionalidade por vez**
3. **Teste suas mudanças** antes de commitar
4. **Adicione comentários** explicando seu código

### 3. Commits
```bash
# Adicione suas mudanças
git add .

# Faça commit com mensagem descritiva
git commit -m "feat: implementa grid de lixeiras no dashboard"

# Push para sua branch
git push origin sua-branch
```

### 4. Pull Request
1. Abra um Pull Request no GitHub
2. Descreva o que foi implementado
3. Solicite review de outros membros
4. Faça ajustes se necessário
5. Merge após aprovação

## Padrões de Código

### Python (Backend)
- Siga PEP 8
- Use docstrings para funções
- Nomes de variáveis em português quando apropriado
- Comentários explicativos

### JavaScript (Frontend)
- Use ES6+
- Nomes de variáveis em inglês
- Comentários para lógica complexa
- Funções pequenas e específicas

### CSS
- Use metodologia BEM
- Variáveis CSS para cores e espaçamentos
- Mobile-first approach
- Comentários para seções

### HTML
- Semântico e acessível
- Comentários para seções
- Estrutura clara e organizada

## Ferramentas Recomendadas

### Desenvolvimento
- **Editor:** VS Code, PyCharm, ou similar
- **Git:** GitHub Desktop ou linha de comando
- **Testes:** Postman para APIs

### Extensões VS Code
- Python
- JavaScript (ES6)
- HTML CSS Support
- GitLens
- Live Server

## Comunicação

### Dúvidas Técnicas
- Use issues no GitHub
- Comente nos Pull Requests
- Reuniões semanais para alinhamento

### Progresso
- Atualize o README com progresso
- Use labels nos commits
- Documente decisões importantes

## Checklist de Qualidade

Antes de fazer commit, verifique:
- [ ] Código funciona sem erros
- [ ] Comentários explicativos adicionados
- [ ] Testes básicos realizados
- [ ] Documentação atualizada
- [ ] Mensagem de commit clara

## Metas por Sprint

### Sprint 1 (Semana 1-2)
- [ ] Estrutura básica funcionando
- [ ] Página principal carregando
- [ ] API básica respondendo
- [ ] Dados mock integrados

### Sprint 2 (Semana 3-4)
- [ ] Grid de lixeiras implementado
- [ ] Filtros funcionando
- [ ] CRUD básico da API
- [ ] Interface responsiva

### Sprint 3 (Semana 5-6)
- [ ] Sistema de alertas
- [ ] Relatórios básicos
- [ ] Testes automatizados
- [ ] Documentação completa

## Problemas Comuns

### "Não consigo rodar o projeto"
- Verifique se instalou as dependências
- Confirme se está na pasta correta
- Leia o README para instruções

### "API não está respondendo"
- Verifique se o Flask está rodando
- Confirme se a porta 5000 está livre
- Teste com Postman ou navegador

### "Mudanças não aparecem"
- Verifique se salvou os arquivos
- Recarregue a página (Ctrl+F5)
- Confirme se está editando o arquivo correto

---

**Lembre-se:** Este é um projeto de aprendizado. Não tenha medo de errar e sempre peça ajuda quando necessário!
