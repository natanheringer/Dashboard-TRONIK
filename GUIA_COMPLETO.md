# Guia de Desenvolvimento - Dashboard-TRONIK

## Sobre este Guia

Este documento cobre o setup completo do projeto e fluxo de trabalho para desenvolvimento em equipe. Assumimos conhecimento básico de programação, mas explicamos ferramentas e processos que podem ser novos.

## Conteúdo

- Setup do ambiente de desenvolvimento
- Git e fluxo de trabalho em equipe
- Estrutura do projeto (HTML, CSS, JavaScript, Python)
- APIs REST com Flask
- Colaboração e code review

---

# PARTE 1: AMBIENTE DE DESENVOLVIMENTO

## 1.1 Terminal/Command Line

O terminal permite executar comandos diretamente no sistema operacional. É essencial para desenvolvimento.

### Acessar Terminal

**Windows:**
- `Windows + R` → digite `powershell` → Enter

**Mac:**
- `Cmd + Espaço` → digite `Terminal` → Enter

**Linux:**
- `Ctrl + Alt + T`

### Comandos essenciais:
```bash
# Ver onde você está
pwd

# Listar arquivos na pasta atual
ls          # Mac/Linux
dir         # Windows

# Entrar em uma pasta
cd nome-da-pasta

# Voltar uma pasta
cd ..

# Criar uma pasta
mkdir nome-da-pasta

# Criar um arquivo
touch nome-do-arquivo.txt    # Mac/Linux
echo. > nome-do-arquivo.txt  # Windows
```

## 1.2 Python

### Verificar instalação:
```bash
python --version
```

### Instalação (se necessário):
1. [python.org](https://www.python.org/downloads/) - baixar versão mais recente
2. **Importante:** Marcar "Add Python to PATH" durante instalação
3. Reiniciar terminal

### Verificar:
```bash
python --version
# Output esperado: Python 3.11.0
```

## 1.3 Git

### Verificar instalação:
```bash
git --version
```

### Instalação (se necessário):
1. [git-scm.com](https://git-scm.com/downloads)
2. Instalar com configurações padrão
3. Reiniciar terminal

### Configuração inicial:
```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu.email@exemplo.com"
```

---

# PARTE 2: ARQUITETURA DO PROJETO

## 2.1 Dashboard-TRONIK

Sistema de monitoramento de lixeiras inteligentes com:
- Visualização em tempo real do nível de preenchimento
- Alertas automáticos
- Relatórios de coleta
- Interface web responsiva

## 2.2 Arquitetura

**Frontend:** Interface do usuário (HTML, CSS, JavaScript)
**Backend:** Lógica de negócio e APIs (Python, Flask)
**Banco de dados:** Armazenamento de dados (SQLite)

## 2.3 Estrutura do projeto

```
Dashboard-TRONIK/
├── app.py                    # Aplicação principal
├── requirements.txt          # Lista de dependências
├── banco_dados/             # Arquivos do banco
├── estatico/                # CSS, JavaScript, imagens
├── templates/               # Páginas HTML
├── rotas/                   # Endpoints da API
└── dados/                   # Dados de exemplo
```

---

# PARTE 3: GIT E COLABORAÇÃO

## 3.1 Git

Sistema de controle de versão que permite:
- Versionamento do código
- Colaboração sem conflitos
- Histórico de mudanças
- Rollback para versões anteriores

## 3.2 Conceitos

**Repositório:** Projeto completo com histórico de versões
**Commit:** Snapshot do código com mensagem descritiva
**Branch:** Linha de desenvolvimento independente
**Pull Request:** Solicitação para integrar mudanças

## 3.3 Fluxo de trabalho

1. Fork do projeto
2. Clone local
3. Criar branch para feature
4. Desenvolver e testar
5. Commit com mensagem clara
6. Push para repositório
7. Pull Request para revisão
8. Code review e merge

---

# PARTE 4: SETUP DO PROJETO

## 4.1 Clone do repositório

```bash
cd Desktop
git clone [URL_DO_REPOSITORIO]
cd Dashboard-TRONIK
```

## 4.2 Ambiente virtual

Isola dependências do projeto:

```bash
# Criar ambiente
python -m venv venv

# Ativar
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

**Indicador:** `(venv)` aparece no prompt quando ativo.

## 4.3 Dependências

```bash
pip install -r requirements.txt
```

## 4.4 Teste

```bash
python app.py
```

**Output esperado:**
```
* Running on http://127.0.0.1:5000
```

Acesse: `http://localhost:5000`

---

# PARTE 5: DIVISÃO DE TRABALHO

## 5.1 Frontend (2-3 pessoas)

**Responsabilidades:**
- Interface web (HTML, CSS, JavaScript)
- Responsividade e UX
- Integração com APIs

**Arquivos:**
- `templates/` - Páginas HTML
- `estatico/css/` - Estilos
- `estatico/js/` - JavaScript
- `estatico/imagens/` - Assets

**Tarefas iniciais:**
1. Template base HTML
2. Estilos CSS responsivos
3. Cards de lixeiras
4. JavaScript para interatividade

**Ferramentas:**
- VS Code + Live Server
- Chrome DevTools

## 5.2 Backend (2 pessoas)

**Responsabilidades:**
- APIs REST (Flask)
- Banco de dados (SQLite)
- Lógica de negócio

**Arquivos:**
- `app.py` - Aplicação principal
- `rotas/` - Endpoints da API
- `banco_dados/` - Modelos e configuração

**Tarefas iniciais:**
1. Configuração Flask
2. Endpoints básicos
3. Conexão com banco
4. CRUD de lixeiras

**Ferramentas:**
- VS Code + Python extension
- Postman

## 5.3 Dados e Testes (2 pessoas)

**Responsabilidades:**
- Dados mock e validação
- Testes automatizados
- Qualidade de dados

**Arquivos:**
- `dados/` - Dados mock
- Testes automatizados

**Tarefas iniciais:**
1. Expandir dados mock
2. Cenários de teste
3. Validação de dados
4. Documentação de casos

## 5.4 Documentação (1 pessoa)

**Responsabilidades:**
- Manutenção da documentação
- Comentários no código
- Guias de uso

**Arquivos:**
- `README.md`
- Comentários inline
- Guias específicos

**Tarefas iniciais:**
1. Atualizar README
2. Comentários no código
3. Guias de uso
4. Documentação de APIs

---

# PARTE 6: COMO COMEÇAR A TRABALHAR

## 6.1 Escolher sua área

Baseado no que você quer aprender:
- **Gosta de design/interface?** → Frontend
- **Gosta de lógica/programação?** → Backend
- **Gosta de organizar/testar?** → Dados e Testes
- **Gosta de escrever/explicar?** → Documentação

## 6.2 Criar sua branch

```bash
# Verificar se está na branch main
git branch

# Criar nova branch para sua área
git checkout -b frontend/interface-principal
# ou
git checkout -b backend/api-basica
# ou
git checkout -b dados/mock-expansion
# ou
git checkout -b docs/readme-update
```

## 6.3 Fazer sua primeira mudança

1. **Escolher um arquivo** da sua área
2. **Ler os comentários TODO** no arquivo
3. **Fazer uma mudança simples**
4. **Testar se funciona**
5. **Fazer commit**

### Exemplo para Frontend:
```bash
# Editar templates/index.html
# Adicionar um título simples
# Salvar o arquivo

# Fazer commit
git add templates/index.html
git commit -m "feat: adiciona título na página principal"
```

### Exemplo para Backend:
```bash
# Editar app.py
# Adicionar uma rota simples
# Salvar o arquivo

# Fazer commit
git add app.py
git commit -m "feat: adiciona rota de status da API"
```

## 6.4 Enviar para revisão

```bash
# Fazer push da sua branch
git push origin sua-branch

# No GitHub, abrir Pull Request
# Explicar o que foi feito
# Solicitar revisão
```

---

# PARTE 7: COMANDOS GIT ESSENCIAIS

## 7.1 Comandos básicos

```bash
# Ver status dos arquivos
git status

# Adicionar arquivos para commit
git add nome-do-arquivo
git add .                    # Adicionar todos os arquivos

# Fazer commit
git commit -m "Sua mensagem aqui"

# Ver histórico de commits
git log

# Ver diferenças
git diff
```

## 7.2 Comandos para trabalhar em equipe

```bash
# Baixar mudanças do repositório
git pull origin main

# Enviar suas mudanças
git push origin sua-branch

# Mudar de branch
git checkout nome-da-branch

# Criar nova branch
git checkout -b nova-branch
```

## 7.3 Resolvendo conflitos

Se aparecer "merge conflict":
1. Abrir o arquivo com conflito
2. Procurar por `<<<<<<<`, `=======`, `>>>>>>>`
3. Escolher qual código manter
4. Remover as marcações de conflito
5. Fazer commit da resolução

---

# PARTE 8: BOAS PRÁTICAS

## 8.1 Mensagens de commit

Use mensagens claras:
```bash
# Bom
git commit -m "feat: adiciona filtro por status de lixeira"
git commit -m "fix: corrige erro na API de lixeiras"
git commit -m "docs: atualiza README com instruções de setup"

# Ruim
git commit -m "mudanças"
git commit -m "fix"
git commit -m "teste"
```

## 8.2 Organização do código

- **Comentários:** Explique o que o código faz
- **Nomes:** Use nomes descritivos para variáveis e funções
- **Estrutura:** Mantenha arquivos organizados
- **Testes:** Teste suas mudanças antes de commitar

## 8.3 Trabalho em equipe

- **Comunique-se:** Use issues no GitHub para dúvidas
- **Seja específico:** Explique exatamente o que fez
- **Peça ajuda:** Não tenha medo de perguntar
- **Revise código:** Ajude outros membros da equipe

---

# PARTE 9: PRIMEIROS PASSOS PRÁTICOS

## 9.1 Para Frontend

### Tarefa 1: Criar página HTML básica
1. Abrir `templates/index.html`
2. Adicionar estrutura HTML básica
3. Incluir título e parágrafo
4. Testar no navegador

### Tarefa 2: Adicionar CSS
1. Abrir `estatico/css/estilo.css`
2. Adicionar estilos básicos
3. Fazer a página ficar bonita
4. Testar responsividade

### Tarefa 3: Adicionar JavaScript
1. Abrir `estatico/js/dashboard.js`
2. Adicionar função para carregar dados
3. Conectar com a API
4. Testar funcionalidade

## 9.2 Para Backend

### Tarefa 1: Configurar Flask
1. Abrir `app.py`
2. Importar Flask
3. Criar aplicação básica
4. Adicionar rota de teste

### Tarefa 2: Criar API básica
1. Abrir `rotas/api.py`
2. Criar blueprint
3. Adicionar endpoint GET
4. Testar com Postman

### Tarefa 3: Conectar banco de dados
1. Abrir `banco_dados/modelos.py`
2. Criar modelo Lixeira
3. Configurar SQLAlchemy
4. Testar conexão

## 9.3 Para Dados e Testes

### Tarefa 1: Expandir dados mock
1. Abrir `dados/sensores_mock.json`
2. Adicionar mais lixeiras
3. Criar diferentes cenários
4. Validar formato JSON

### Tarefa 2: Criar testes
1. Criar arquivo de testes
2. Testar endpoints da API
3. Validar dados
4. Documentar casos de teste

## 9.4 Para Documentação

### Tarefa 1: Atualizar README
1. Abrir `README.md`
2. Adicionar seção de progresso
3. Documentar novas funcionalidades
4. Atualizar instruções

### Tarefa 2: Adicionar comentários
1. Revisar todos os arquivos
2. Adicionar comentários explicativos
3. Documentar funções
4. Criar guias específicos

---

# PARTE 10: RECURSOS DE APRENDIZADO

## 10.1 Tutoriais recomendados

### HTML/CSS/JavaScript
- [MDN Web Docs](https://developer.mozilla.org/)
- [W3Schools](https://www.w3schools.com/)
- [FreeCodeCamp](https://www.freecodecamp.org/)

### Python/Flask
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Python.org Tutorial](https://docs.python.org/3/tutorial/)
- [Real Python](https://realpython.com/)

### Git
- [Git Handbook](https://guides.github.com/introduction/git-handbook/)
- [Atlassian Git Tutorial](https://www.atlassian.com/git/tutorials)

## 10.2 Ferramentas úteis

### Editores de código
- **VS Code** (recomendado)
- **Sublime Text**
- **Atom**

### Extensões VS Code
- Python
- HTML CSS Support
- Live Server
- GitLens
- Prettier

### Testes
- **Postman** (para APIs)
- **DB Browser for SQLite** (para banco)
- **Chrome DevTools** (para frontend)

---

# PARTE 11: CRONOGRAMA SUGERIDO

## Semana 1: Setup e Primeiros Passos
- [ ] Instalar ferramentas
- [ ] Configurar ambiente
- [ ] Entender o projeto
- [ ] Fazer primeira mudança

## Semana 2: Desenvolvimento Básico
- [ ] Implementar funcionalidades básicas
- [ ] Testar mudanças
- [ ] Fazer commits regulares
- [ ] Abrir primeiro Pull Request

## Semana 3: Integração
- [ ] Conectar frontend com backend
- [ ] Testar integração
- [ ] Resolver bugs
- [ ] Melhorar documentação

## Semana 4: Finalização
- [ ] Testes finais
- [ ] Documentação completa
- [ ] Apresentação do projeto
- [ ] Reflexão sobre aprendizado

---

# PARTE 12: DÚVIDAS FREQUENTES

## "Não consigo instalar Python"
- Verifique se marcou "Add to PATH"
- Reinicie o terminal
- Tente usar `python3` em vez de `python`

## "Git não funciona"
- Verifique se está configurado: `git config --list`
- Configure nome e email: `git config --global user.name "Seu Nome"`

## "Não consigo rodar o projeto"
- Ative o ambiente virtual: `venv\Scripts\activate`
- Instale dependências: `pip install -r requirements.txt`
- Execute: `python app.py`

## "Não sei por onde começar"
- Leia os comentários TODO nos arquivos
- Escolha uma tarefa simples
- Peça ajuda no GitHub Issues
- Comece com mudanças pequenas

## "Como sei se estou fazendo certo?"
- Teste suas mudanças
- Peça revisão de outros membros
- Compare com exemplos online
- Não tenha medo de errar

---

# CONCLUSÃO

Este guia cobre tudo que você precisa saber para começar no projeto Dashboard-TRONIK. Lembre-se:

1. **Não tenha medo de errar** - Erros são parte do aprendizado
2. **Peça ajuda** - A equipe está aqui para se ajudar
3. **Comece simples** - Faça mudanças pequenas primeiro
4. **Teste sempre** - Verifique se suas mudanças funcionam
5. **Comunique-se** - Use o GitHub para conversar com a equipe

**Boa sorte e bom aprendizado!**
