# Tomate Monitor - Projeto do TCC

Sistema web para monitoramento agrícola e detecção precoce de doenças em folhas de
tomate. A aplicação registra capturas e leituras ambientais, processa imagens com
MobileSAM e MobileNetV2 e gera alertas conforme o resultado e as condições ambientais.

## Requisitos

- Python 3.12 ou superior
- MySQL Community Server 8.4 LTS
- Navegador com acesso à internet para carregar Bootstrap e Chart.js por CDN

## Instalação no Windows

```powershell
uv venv --python 3.12 .venv
$env:UV_CACHE_DIR=(Join-Path (Get-Location) '.uv-cache')
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Acesse `http://127.0.0.1:8000/` e entre com o e-mail e a senha cadastrados.

Antes da migração, preencha no `.env` a chave do Django e as credenciais do banco.
O MySQL é obrigatório; o sistema não usa mais SQLite. As configurações disponíveis
estão documentadas em `.env.example`. Não copie senhas, chaves ou credenciais reais
para arquivos versionados.

Para visualizar a base no MySQL Workbench, crie uma conexão com host `127.0.0.1`,
porta `3306`, usuário `agromonitor_app` e o schema padrão `agromonitor`. Use a senha
definida em `DB_PASSWORD` no seu `.env`. Os dados operacionais ficam nas tabelas com
prefixos `captures_`, `predictions_`, `sensors_` e `alerts_`; usuários e sessões ficam
em `accounts_user` e `django_session`.

## Dados demonstrativos

Depois de criar o usuário, gere uma base simulada:

```powershell
.venv\Scripts\python.exe manage.py seed_demo --email seu@email.com --count 12
```

## API REST

Os endpoints usam a sessão do Django e exigem autenticação:

- `POST /api/captures/`
- `POST /api/predictions/`
- `GET /api/dashboard/summary/`
- `GET /api/alerts/`

Exemplo de captura: `{"device_identifier":"ESTUFA-01","observation":"Amostra","temperature":"25.00","humidity":"86.00"}`.
Durante a transição, o identificador pode ser omitido quando o usuário possui um
único dispositivo ativo. Temperatura ou umidade nula é registrada como zero.

O envio da captura executa automaticamente o pré-processamento e a inferência. A
requisição aguarda a conclusão da análise antes de responder. O endpoint de predição
continua disponível para processamentos manuais de capturas existentes com
`{"capture_id":1}`.
