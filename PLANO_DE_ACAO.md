# Plano de ação — MVP do Monitoramento Agrícola

## Objetivo

Construir um MVP em Django com autenticação por e-mail, dashboard, capturas e leituras ambientais simuladas, processamento fictício, histórico, alertas e uma estrutura inicial de API REST. IA, ESP32-CAM e DHT22 reais ficam fora desta versão.

## Decisões técnicas

- Python 3.12+ e Django 5.2 LTS.
- SQLite no MVP, com configuração preparada para MySQL por variáveis de ambiente.
- Django REST Framework para os endpoints.
- Bootstrap 5 e Chart.js no frontend.
- Serviços de domínio compartilhados entre as telas e a API.

## Etapas de implementação

- [x] Criar estrutura Django, dependências e configurações.
- [x] Implementar usuário por e-mail, models, admin e migrations.
- [x] Implementar geração simulada e regras de alerta.
- [x] Implementar login, dashboard, capturas, resultados, histórico e alertas.
- [x] Implementar endpoints REST autenticados.
- [x] Criar comando de dados demonstrativos e documentação de execução.
- [x] Executar testes automatizados e registrar o resultado.

## Regras funcionais

- Confiança menor que 60%: alerta de baixa confiança.
- Doença com confiança a partir de 80%: alerta fitossanitário.
- Doença com confiança a partir de 80% e umidade a partir de 85%: alerta crítico.
- Umidade a partir de 85%: alerta ambiental.
- Classe saudável nunca gera alerta fitossanitário.
- O processamento é idempotente: uma captura possui no máximo uma predição.
- Alertas ativos são os ainda não visualizados.
- Cada usuário acessa somente os próprios registros.

## Contratos previstos

- `POST /api/captures/`
- `POST /api/predictions/`
- `GET /api/dashboard/summary/`
- `GET /api/alerts/`

## Critérios de aceite

- Fluxo login → captura → leitura → processamento → resultado → alerta → histórico funcional.
- Dashboard apresenta indicadores e gráficos com dados persistidos.
- Filtros e paginação funcionam no histórico e nos alertas.
- Rotas web e API exigem autenticação e isolam dados por usuário.
- Migrations, carga demonstrativa e testes executam sem IA ou hardware reais.

## Evidências de validação

- Ambiente criado com CPython 3.12.13 por meio do `uv`.
- `manage.py migrate`: todas as migrations aplicadas com sucesso em SQLite.
- `manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- `manage.py check`: nenhuma inconsistência encontrada.
- `manage.py test --verbosity 2`: 13 testes executados e aprovados.
- `compileall`: módulos Python compilados sem erro de sintaxe.
- Bootstrap e Chart.js dependem de internet por serem carregados via CDN.
- A configuração padrão é de desenvolvimento; antes de produção devem ser definidos segredo, hosts, HTTPS e armazenamento apropriado.
