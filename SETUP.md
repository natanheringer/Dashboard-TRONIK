# Guia de Setup - Dashboard-TRONIK

## Pré-requisitos

### 1. Python 3.8 ou Superior
**Verificar se está instalado:**
```bash
python --version
# ou
python3 --version
```

**Se não tiver Python:**
- Windows: Baixe em [python.org](https://www.python.org/downloads/)
- Mac: Use Homebrew: `brew install python3`
- Linux: `sudo apt install python3 python3-pip`

### 2. Git
**Verificar se está instalado:**
```bash
git --version
```

**Se não tiver Git:**
- Windows: Baixe em [git-scm.com](https://git-scm.com/download/win)
- Mac: `brew install git`
- Linux: `sudo apt install git`

## Setup do Projeto

### 1. Clonar o Repositório
```bash
git clone [URL_DO_REPOSITORIO]
cd Dashboard-TRONIK
```

### 2. Criar Ambiente Virtual (Recomendado)
**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Verificar Instalação
```bash
python -c "import flask, flask_cors, sqlalchemy; print('Todas as dependências instaladas!')"
```

## Executar o Projeto

### 1. Iniciar o Servidor
```bash
python app.py
```

### 2. Acessar o Dashboard
Abra seu navegador e acesse: `http://localhost:5000`

## Estrutura de Desenvolvimento

### Para Frontend (HTML/CSS/JS)
- Trabalhe nos arquivos em `templates/` e `estatico/`
- Use Live Server no VS Code para ver mudanças em tempo real
- Teste no navegador acessando `http://localhost:5000`

### Para Backend (Python/Flask)
- Trabalhe nos arquivos em `app.py`, `rotas/`, `banco_dados/`
- O Flask tem auto-reload ativado (mudanças aparecem automaticamente)
- Teste APIs com Postman ou navegador

### Para Dados
- Trabalhe com `dados/sensores_mock.json`
- Use ferramentas como DB Browser for SQLite para visualizar banco

## Ferramentas Recomendadas

### Editores
- **VS Code** (recomendado)
  - Extensões: Python, HTML CSS Support, Live Server
- **PyCharm** (para Python)
- **Sublime Text** ou **Atom**

### Testes de API
- **Postman** (interface gráfica)
- **curl** (linha de comando)
- **Navegador** (para GET requests)

### Banco de Dados
- **DB Browser for SQLite** (interface gráfica)
- **SQLite CLI** (linha de comando)

## Comandos Úteis

### Git
```bash
# Ver status
git status

# Adicionar arquivos
git add .

# Fazer commit
git commit -m "Sua mensagem aqui"

# Push para repositório
git push origin sua-branch
```

### Python
```bash
# Executar aplicação
python app.py

# Instalar nova dependência
pip install nome-da-biblioteca

# Ver dependências instaladas
pip list

# Atualizar requirements.txt
pip freeze > requirements.txt
```

### Debugging
```bash
# Ver logs detalhados
python app.py --debug

# Testar importações
python -c "import flask; print(flask.__version__)"
```

## Problemas Comuns

### "Python não encontrado"
- Verifique se Python está no PATH
- Tente `python3` em vez de `python`
- Reinstale Python marcando "Add to PATH"

### "pip não encontrado"
- Instale pip: `python -m ensurepip --upgrade`
- Ou use: `python -m pip install -r requirements.txt`

### "Porta 5000 em uso"
- Mude a porta no `app.py`: `app.run(port=5001)`
- Ou mate o processo: `netstat -ano | findstr :5000`

### "Módulo não encontrado"
- Ative o ambiente virtual
- Reinstale dependências: `pip install -r requirements.txt`

### "CORS errors no navegador"
- Verifique se Flask-CORS está instalado
- Confirme se está configurado no `app.py`

## Próximos Passos

1. **Leia o README.md** para entender o projeto
2. **Consulte o GUIA_CONTRIBUICAO.md** para sua área
3. **Comece com arquivos simples** (templates básicos)
4. **Teste cada mudança** antes de continuar
5. **Faça commits frequentes** com mensagens claras

## Suporte

- **Issues no GitHub** para bugs
- **Pull Requests** para contribuições
- **Reuniões da equipe** para dúvidas
- **Documentação** sempre atualizada

---

**Dica:** Mantenha este arquivo atualizado conforme o projeto evolui!
