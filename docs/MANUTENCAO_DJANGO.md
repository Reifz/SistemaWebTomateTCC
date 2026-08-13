# Guia simples de manutenção do projeto Django

## 1. Organização

O Django divide o sistema em um **projeto** e vários **aplicativos**.

- `agromonitor/`: configurações gerais e URLs principais.
- `accounts/`: usuários e administração de contas.
- `captures/`: cadastro e consulta de capturas.
- `sensors/`: temperatura e umidade de cada captura.
- `predictions/`: análise simulada e histórico das predições.
- `alerts/`: regras e visualização de alertas.
- `dashboard/`: resumos da página inicial e do painel.
- `api/`: endpoints JSON para integrações.
- `templates/`: páginas HTML.
- `static/`: arquivos CSS.
- `media/`: imagens enviadas pelo formulário.
- `resultados/`: arquivos produzidos externamente pela IA.

Em cada aplicativo, os arquivos mais importantes são:

- `models.py`: estrutura dos dados;
- `views.py`: recebe a requisição e prepara a resposta;
- `urls.py`: liga uma URL a uma view;
- `forms.py`: valida formulários;
- `services.py`: concentra regras de negócio;
- `tests.py`: testes automáticos;
- `admin.py`: configura o painel administrativo;
- `migrations/`: histórico das alterações do banco.

## 2. Caminho de uma requisição

Quando alguém abre `/captures/`:

1. `agromonitor/urls.py` encaminha a URL para `captures/urls.py`.
2. `captures/urls.py` escolhe uma função de `captures/views.py`.
3. A view consulta o modelo `Capture`.
4. A view chama `render()` e envia dados para `templates/captures/list.html`.
5. O template produz o HTML que chega ao navegador.

Nomes como `request`, `GET`, `POST`, `Model`, `objects`, `filter`, `save` e `render` pertencem à API do Django e não devem ser traduzidos.

## 3. Fluxo de uma captura

O formulário usa `FormularioCaptura`, em `captures/forms.py`.

1. A view cria uma `Capture`.
2. `gerar_leitura_ambiental()` cria uma leitura simulada.
3. A captura começa como pendente.
4. Ao analisar, `processar_captura()` cria uma `Prediction`.
5. `criar_alertas_da_predicao()` aplica as regras de alerta.
6. A captura passa para processada.

Hoje `processar_captura()` simula o resultado. Para integrar a IA real, substitua o conteúdo dessa função e preserve o retorno `(predicao, criada)`.

## 4. Banco de dados

O desenvolvimento usa `db.sqlite3`. O projeto também aceita MySQL pelas variáveis descritas no `README.md`.

Os modelos mantêm seus nomes existentes (`Capture`, `Prediction`, `Alert`, `EnvironmentalReading` e `User`) porque eles já aparecem em migrações, consultas, templates e respostas da API. Renomeá-los exige uma migração planejada; uma troca direta pode ser interpretada como exclusão e criação de tabelas.

Depois de alterar um modelo:

```powershell
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate
```

Leia a migração gerada antes de aplicá-la e faça backup do banco de produção.

## 5. Alterações comuns

### Alterar uma página

Edite o template em `templates/`. A estrutura geral fica em `templates/base.html` e o visual em `static/css/app.css`.

### Alterar uma regra de alerta

Edite `criar_alertas_da_predicao()` em `alerts/services.py`.

### Alterar as classes reconhecidas

Edite `CLASSES_TOMATE` em `predictions/services.py`. Os valores precisam coincidir com as classes do modelo treinado.

### Alterar filtros

Edite a view e o template da listagem. O valor de `request.GET` deve ter o mesmo nome do atributo `name` do campo HTML.

### Criar uma página

1. Crie uma função em `views.py`.
2. Registre-a em `urls.py`.
3. Crie o template.
4. Escreva um teste que acesse a rota.

## 6. Comandos de rotina

```powershell
# Ativar o ambiente e iniciar o servidor
.venv\Scripts\Activate.ps1
python manage.py runserver

# Verificar o projeto e executar os testes
python manage.py check
python manage.py test

# Criar administrador
python manage.py createsuperuser

# Criar dados demonstrativos
python manage.py seed_demo --email seu-email@exemplo.com --count 12
```

## 7. Manutenção segura

- Faça uma alteração pequena por vez.
- Execute `manage.py check` e `manage.py test` após alterar o projeto.
- Não edite migrações antigas; gere uma nova migração.
- Não coloque regras de negócio grandes nos templates.
- Use `services.py` para regras usadas por páginas e API.
- Preserve campos JSON enquanto existirem clientes da API.
- Não publique `SECRET_KEY`, senhas ou credenciais.
- Em produção, use `DEBUG=0`, configure `ALLOWED_HOSTS` e faça backup antes de migrar.

## 8. Ordem recomendada para estudar

1. `agromonitor/urls.py`
2. `captures/urls.py`
3. `captures/views.py`
4. `captures/forms.py`
5. `captures/models.py`
6. `templates/captures/`
7. `predictions/services.py`
8. `alerts/services.py`
9. os arquivos `tests.py`

Essa sequência mostra como URL, view, formulário, banco, regra e HTML se conectam.

## 9. Como o Dashboard e os gráficos funcionam

O Dashboard é dividido em quatro responsabilidades:

1. `dashboard/views.py` identifica o usuário e chama o serviço.
2. `dashboard/services.py` consulta o banco e monta indicadores e séries.
3. `templates/dashboard/index.html` define os cards, tabelas e elementos `canvas`.
4. `static/js/dashboard-graficos.js` lê os dados JSON e configura o Chart.js.

Os dados são enviados do Python ao JavaScript com a tag `json_script` do Django.
Essa tag evita montar JSON manualmente dentro de um `<script>` e protege caracteres
especiais. O identificador usado no template deve ser o mesmo lido por
`lerDadosJson()` no JavaScript.

Para alterar um gráfico existente:

1. encontre sua agregação em `dashboard/services.py`;
2. confira a chave adicionada ao dicionário de `resumo_dashboard()`;
3. encontre o `json_script` e o `canvas` em `dashboard/index.html`;
4. altere somente a função `criarGrafico...()` correspondente no JavaScript;
5. atualize ou crie um teste em `dashboard/tests.py`.

As funções iniciadas com `_` no serviço são auxiliares internas. Elas existem para
separar assuntos como acesso do usuário, confiança por classe, alertas por data e
faixas de umidade. Mantenha novas agregações em funções pequenas semelhantes.

## 10. Padrão de leitura do frontend

- HTML usa indentação de dois espaços e uma tag por nível visual.
- CSS é agrupado por componente: navbar, painéis, cards, tabelas e responsividade.
- JavaScript usa uma função nomeada para cada gráfico.
- Constantes compartilhadas ficam no início do arquivo JavaScript.
- Textos e nomes próprios do projeto ficam em português.
- Nomes exigidos por Django, Chart.js, APIs e campos já publicados são preservados.

Formatadores usados nesta revisão:

```powershell
# Templates Django
uvx djhtml -t 2 templates

# JavaScript e CSS
npx --yes prettier@3.6.2 --write static/js/dashboard-graficos.js static/css/app.css static/css/responsivo.css
```

Depois de formatar, sempre execute os testes, pois templates podem depender da
posição de tags Django e blocos condicionais.
