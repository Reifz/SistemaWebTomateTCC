# AgroMonitor — MVP do TCC

Para entender a estrutura e realizar manutenção, consulte o [guia de manutenção Django](docs/MANUTENCAO_DJANGO.md).

Protótipo funcional do sistema de monitoramento agrícola e detecção precoce de doenças em folhas de tomate. Esta versão usa capturas, sensores, predições e alertas simulados; não executa IA real nem recebe dados de hardware.

## Requisitos

- Python 3.12 ou superior
- Navegador com acesso à internet para carregar Bootstrap e Chart.js por CDN

## Instalação no Windows

```powershell
uv venv --python 3.12 .venv
$env:UV_CACHE_DIR=(Join-Path (Get-Location) '.uv-cache')
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Acesse `http://127.0.0.1:8000/` e entre com o e-mail e a senha cadastrados.

As configurações disponíveis estão documentadas em `.env.example`. Não copie
senhas, chaves ou credenciais reais para arquivos versionados.

## Dados demonstrativos

Depois de criar o usuário, gere uma base simulada:

```powershell
.venv\Scripts\python.exe manage.py seed_demo --email seu@email.com --count 12
```

## Testes

```powershell
.venv\Scripts\python.exe manage.py test
```

## API REST

Os endpoints usam a sessão do Django e exigem autenticação:

- `POST /api/captures/`
- `POST /api/predictions/`
- `GET /api/dashboard/summary/`
- `GET /api/alerts/`

Exemplo de captura: `{"observation":"Amostra","temperature":"25.00","humidity":"86.00"}`. Para processar: `{"capture_id":1}`.

A estrutura inicial da API está pronta para a continuidade do projeto. Enquanto a
integração não for concluída, os endpoints de captura e predição respondem com HTTP
`501 Not Implemented` e não gravam dados provisórios. Os comentários em `api/views.py`
indicam as etapas esperadas para conectar o ESP32-CAM, o sensor e o modelo.

## Configuração futura do MySQL

Defina `DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` e `DB_PORT`, além de instalar um driver Django/MySQL compatível. SQLite permanece o padrão do protótipo.

## Próximas etapas

1. Autenticar o ESP32-CAM e receber imagem e telemetria reais.
2. Trocar armazenamento local por armazenamento adequado ao ambiente de produção.
3. Implementar pré-processamento e adaptador de inferência MobileNetV2.
4. Executar processamento pesado em fila assíncrona.
5. Integrar os serviços reais de sensores e inferência preservando os contratos das views e da API.

## Colaboração

As instruções para criar branches, commits e publicar o projeto estão em
[`github.md`](github.md). Todo Pull Request para `main` executa os testes
automaticamente pelo GitHub Actions.
