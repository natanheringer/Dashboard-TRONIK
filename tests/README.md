# Testes - Dashboard-TRONIK

Este diretório contém os testes automatizados do projeto.

## Estrutura

```
tests/
├── __init__.py              # Pacote de testes
├── conftest.py              # Configuração compartilhada do pytest
├── test_auth.py             # Testes de autenticação
├── test_api_lixeiras.py     # Testes da API de lixeiras
└── README.md                # Este arquivo
```

## Como Executar

### Instalar Dependências

```bash
pip install -r requirements.txt
```

### Executar Todos os Testes

```bash
pytest
```

### Executar Testes Específicos

```bash
# Apenas testes de autenticação
pytest tests/test_auth.py

# Apenas testes da API
pytest tests/test_api_lixeiras.py

# Teste específico
pytest tests/test_auth.py::TestLogin::test_login_success_json
```

### Executar com Cobertura

```bash
pytest --cov=. --cov-report=html --cov-report=term-missing
```

Isso gerará um relatório de cobertura em `htmlcov/index.html`.

### Modo Verboso

```bash
pytest -v
```

### Parar no Primeiro Erro

```bash
pytest -x
```

## Estrutura dos Testes

### Fixtures Disponíveis

- `test_db`: Banco de dados temporário para testes
- `db_session`: Sessão do banco para cada teste
- `client`: Cliente Flask para requisições HTTP
- `auth_headers`: Headers de autenticação para usuário comum
- `admin_headers`: Headers de autenticação para admin
- `sample_lixeira_data`: Dados de exemplo para criar lixeiras

### Exemplo de Teste

```python
def test_exemplo(client, db_session):
    """Exemplo de teste"""
    # Fazer login
    usuario = Usuario(username='test', email='test@example.com')
    usuario.set_senha('pass123')
    db_session.add(usuario)
    db_session.commit()
    
    # Fazer requisição
    response = client.post('/auth/login', json={
        'username': 'test',
        'senha': 'pass123'
    })
    
    # Verificar resultado
    assert response.status_code == 200
```

## Boas Práticas

1. **Isolamento**: Cada teste deve ser independente
2. **Limpeza**: O banco é limpo automaticamente após cada teste
3. **Nomes Descritivos**: Use nomes que descrevam o que está sendo testado
4. **AAA Pattern**: Arrange (preparar), Act (executar), Assert (verificar)

## Cobertura Atual

- ✅ Autenticação (login, registro, logout)
- ✅ API de Lixeiras (listar, criar, obter)
- ⏳ API de Coletas (em desenvolvimento)
- ⏳ Validações (em desenvolvimento)
- ⏳ Geocodificação (em desenvolvimento)

## Próximos Passos

1. Adicionar testes de atualização e exclusão de lixeiras
2. Adicionar testes de coletas
3. Adicionar testes de validação
4. Adicionar testes de geocodificação
5. Adicionar testes de integração



