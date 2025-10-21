# Dashboard-TRONIK

## Sobre o Projeto

O Dashboard-TRONIK é um sistema de monitoramento de coletores inteligentes que permite visualizar em tempo real o nível de preenchimento e status de cada lixeira equipada com sensores ultrassônicos.

## Objetivo

Desenvolver uma solução web completa para monitoramento de coletores, permitindo que a equipe aprenda desenvolvimento web moderno através de um projeto real e prático.

## Stack Tecnológico

- **Frontend:** HTML5 + CSS3 + JavaScript (vanilla)
- **Backend:** Python Flask
- **Banco de Dados:** SQLite
- **Comunicação:** REST API + polling simples

## Estrutura do Projeto

```
dashboard-tronik/
├── app.py                    # Aplicação Flask principal
├── requirements.txt          # Dependências Python
├── banco_dados/             # Configuração e modelos do banco
│   ├── modelos.py           # Modelos de dados (Lixeira, Sensor)
│   └── inicializar.py       # Setup inicial do banco de dados
├── estatico/                # Arquivos estáticos (CSS, JS, imagens)
│   ├── css/
│   │   └── estilo.css       # Estilos do dashboard
│   ├── js/
│   │   ├── dashboard.js     # Lógica principal do dashboard
│   │   └── api.js           # Comunicação com backend
│   └── imagens/             # Imagens e ícones
├── templates/               # Templates HTML
│   ├── index.html           # Página principal do dashboard
│   └── base.html            # Template base
├── rotas/                   # Definição de rotas
│   ├── api.py               # Endpoints da API REST
│   └── paginas.py           # Rotas das páginas web
└── dados/                   # Dados de exemplo e mock
    └── sensores_mock.json   # Dados mock dos sensores
```

## Como Começar

### Para Iniciantes
Se você nunca trabalhou com desenvolvimento web, Git, ou em equipe, comece aqui:
**[GUIA_DESENVOLVIMENTO.md](GUIA_DESENVOLVIMENTO.md)** - Setup completo e fluxo de trabalho

### Para Quem Já Tem Experiência
Se você já sabe usar terminal e Git:

```bash
# Clone o repositório
git clone [URL_DO_REPOSITORIO]
cd Dashboard-TRONIK

# Instale as dependências Python
pip install -r requirements.txt

# Execute a aplicação
python app.py
```

### Acesse o Dashboard
Abra seu navegador e acesse: `http://localhost:5000`

## Organização da Equipe

A equipe deve se auto-organizar baseada nos interesses e habilidades de cada membro. O projeto permite diferentes abordagens:

### Áreas de Desenvolvimento
- **Frontend:** Interface web (HTML, CSS, JavaScript)
- **Backend:** APIs e lógica (Python, Flask, SQLite)
- **Dados:** Mock data, testes e validação
- **Documentação:** README, comentários e guias

### Como Começar
1. Leia o [GUIA_DESENVOLVIMENTO.md](GUIA_DESENVOLVIMENTO.md)
2. Explore a estrutura do projeto
3. Escolha uma área baseada no seu interesse
4. Comece com tarefas simples
5. Colabore com outros membros conforme necessário

## Funcionalidades Planejadas

- [ ] Dashboard visual com grid de lixeiras
- [ ] API REST para CRUD de sensores
- [ ] Simulação de mudança de nível em tempo real
- [ ] Sistema de alertas (nível > 80%)
- [ ] Relatórios básicos de coletas
- [ ] Interface responsiva para mobile

## Desenvolvimento

### Padrões de Código
- **Python:** PEP 8
- **JavaScript:** ES6+
- **CSS:** BEM methodology
- **Commits:** Conventional Commits

### Fluxo de Trabalho
1. Criar branch para feature
2. Desenvolver com testes
3. Code review
4. Merge para main

## Licença

Este projeto está sob a licença GPL-2.0. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Contribuindo

1. Faça fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Contribuidores

Veja a lista completa de contribuidores em [CONTRIBUTORS.md](CONTRIBUTORS.md).

## Contato

Para dúvidas sobre o projeto, entre em contato com a equipe de desenvolvimento.

---

**Nota:** Este é um projeto acadêmico focado no aprendizado de desenvolvimento web.