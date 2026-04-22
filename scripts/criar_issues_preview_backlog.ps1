# Cria issues de backlog no GitHub apos: gh auth login
# Uso: .\scripts\criar_issues_preview_backlog.ps1
$ErrorActionPreference = "Stop"
$Repo = "natanheringer/dashboard-tronik"
$gh = Join-Path ${env:ProgramFiles} "GitHub CLI\gh.exe"
if (-not (Test-Path $gh)) { $gh = "gh" }

function Submit-Issue([string]$Title, [string]$Body) {
    $Body | & $gh issue create --repo $Repo --title $Title --body-file -
    if ($LASTEXITCODE -ne 0) { throw "gh issue create falhou. Execute: gh auth login" }
}

Submit-Issue "Preview v2: migrar Configuracoes para shell v2" @'
Objetivo: fluxo nativo em /preview para gestao atualmente em /configuracoes (CRUD coletores/coletas/sensores), reutilizando APIs existentes.

Criterios: paridade funcional com templates/configuracoes.html; UI com tokens v2.

Fora de escopo: mudanca de schema sem discussao.
'@

Submit-Issue "Preview v2: modulo Notificacoes" @'
Objetivo: pagina de notificacoes no preview alinhada a /api/notificacoes e fluxo de processar alertas.

Criterios: lista e filtros equivalentes ao legado onde fizer sentido na UX v2.
'@

Submit-Issue "Preview v2: mapa — rotas OSRM e export PNG" @'
Contexto: mapa preview ja tem cluster, filtros GET, sede opcional e PreviewMapa.updateMarker.

Falta paridade com mapa.js: OSRM/Routing Machine, export PNG (mapa/exportacao.js), filtros por distancia da sede.

Criterios: CSP documentada em app.py; fallback quando OSRM falhar (comportamento explicito).
'@

Submit-Issue "Preview v2: Relatorios — tipo operacao e export sem legado" @'
Contexto: preview/relatorios ainda usa botao para modulo legado. Legado filtra tipo operacao (Avulsa/Campanha).

Criterios: filtro em preview_service/resumo; export CSV minimo sem depender de /relatorios legado no fluxo feliz.
'@

Submit-Issue "Preview v2: toolbar global (atualizar / simular / export CSV)" @'
Contexto: base.html tem btn-atualizar, simular, exportar; base_v2 nao.

Criterios: decisao de produto (implementar vs nao); simular apenas em development ou admin.
'@

Write-Host "OK. Issues criadas em https://github.com/$Repo/issues"
