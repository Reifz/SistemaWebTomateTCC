# Publicação no GitHub

Repositório previsto: `https://github.com/Reifz/SistemaWebTomateTCC`.

## Antes do primeiro envio

Execute os testes e confirme que nenhum arquivo pessoal ou credencial aparece na
lista produzida por `git status`.

```powershell
.venv\Scripts\python.exe manage.py test
git status --short
```

Não publique `.env`, `db.sqlite3`, arquivos de `media/` nem saídas de
`resultados/`. Esses caminhos já estão configurados no `.gitignore`.

## Criar o repositório local

Execute apenas uma vez:

```powershell
git init
git branch -M main
git remote add origin https://github.com/Reifz/SistemaWebTomateTCC.git
```

## Primeiro envio

```powershell
git add -A
git commit -m "Preparar projeto para colaboração"
git push -u origin main
```

## Trabalho em equipe

Cada integrante deve criar uma branch para sua alteração:

```powershell
git switch -c nome-da-alteracao
git add -A
git commit -m "Descrever alteração"
git push -u origin nome-da-alteracao
```

Depois, deve abrir um Pull Request no GitHub para revisão antes de integrar a
alteração à branch `main`.





erro git

fatal: detected dubious ownership in repository at 'C:/Users/Gui/Documents/proje
toTcc/Dashboard_Tcc'
'C:/Users/Gui/Documents/projetoTcc/Dashboard_Tcc/.git' is owned by:
        DESKTOP-U7SJUPR/CodexSandboxOffline (S-1-5-21-249607603-3267112483-31411
94386-1003)
but the current user is:
        DESKTOP-U7SJUPR/Gui (S-1-5-21-249607603-3267112483-3141194386-1001)
To add an exception for this directory, call:

        git config --global --add safe.directory C:/Users/Gui/Documents/projetoT
cc/Dashboard_Tcc
