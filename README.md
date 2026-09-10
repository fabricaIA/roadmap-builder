# RoadmapBuilder

Gera milestones, issues e roadmap executável no GitHub para o plano de execução do processo da Fábrica.

## Aplicação web (multiusuário)

Além da CLI, há uma aplicação web (`backend/app` + `frontend/`) com login via GitHub
OAuth. Cada usuário guarda o próprio **PAT** e configurações no perfil; o roadmap é
criado com esse PAT.

### Pré-requisitos

1. **OAuth App do GitHub** (Settings → Developer settings → OAuth Apps).
   Authorization callback URL (dev): `http://localhost:8000/api/auth/github/callback`.
2. Copie `.env.example` para `.env` e preencha `GITHUB_OAUTH_CLIENT_ID/SECRET`,
   `SESSION_SECRET` e `PAT_ENCRYPTION_KEY`:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

### Rodar (dev)

```bash
# backend
python -m pip install -r requirements-dev.txt
alembic upgrade head                       # cria/atualiza o banco (SQLite por padrão)
uvicorn backend.app.main:app --reload --port 8000

# frontend (outro terminal) — o Vite faz proxy de /api para :8000
cd frontend && npm install && npm run dev
```

Abra `http://localhost:5173`, entre com o GitHub, configure o PAT no perfil
(`repo` + `project`) e crie o roadmap pelo wizard.

### Multi-tenant e dashboards

O tenant é a **organização do GitHub**: no login (escopo `read:org`) o app
sincroniza suas orgs e o papel (`admin` → coordenador, `member` → dev).
Selecione a org no cabeçalho. Cada usuário vê:

- **Minhas issues** — issues (autor/assignee) nos projetos de roadmap da org.
- **Issues da organização** — todas as issues dos projetos da org.
- **Devs** (só coordenador) — progresso por desenvolvedor e por fase.

Os números são buscados live no GitHub (cache de 60s). Se o PAT não tiver
`read:org`, sincronize manualmente pelo perfil.

Testes do backend: `pytest`.

## Automação por linha de comando (CLI)

Para facilitar a criação do **Project (quadro)**, **milestones** e **issues**, este repositório inclui:

- `backlog_github_project.json`: backlog e estrutura de labels/marcos.
- `scripts/roadmap_builder.py`: automação principal para provisionar no GitHub.
- `scripts/bootstrap_github_project.py`: wrapper de compatibilidade para comandos antigos.

### 1) Simular (dry-run)

```bash
python3 scripts/roadmap_builder.py --owner <OWNER_REPO> --repo <NOME_REPO>
```

### 2) Aplicar de fato no GitHub

```bash
export GITHUB_TOKEN=<SEU_TOKEN>
python3 scripts/roadmap_builder.py --owner <OWNER_REPO> --repo <NOME_REPO> --apply
```

### Criar apenas as issues de uma fase

`--phase` cria só as issues do milestone indicado (repita para várias). As
milestones e labels continuam sendo garantidas por inteiro. É idempotente:
reexecutar não duplica issues (as existentes são atualizadas).

```bash
python3 scripts/roadmap_builder.py --owner <OWNER> --repo <REPO> --apply --phase M1
# depois:
python3 scripts/roadmap_builder.py --owner <OWNER> --repo <REPO> --apply --phase M2
```

Na aplicação web isso aparece no detalhe do projeto (botão "Aplicar Fase" por
fase, com aviso ou no-op quando a fase já existe).

### Definir cronograma estimado

Informe a data prevista de início do projeto para o script calcular as datas em sequência:

```bash
python3 scripts/roadmap_builder.py --owner <OWNER_REPO> --repo <NOME_REPO> --project-start-date 2026-05-01
```

Ao usar `--apply`, o script:

- calcula janelas sequenciais para os milestones, na ordem definida em `milestones`;
- preenche a data alvo (`due_on`) de cada milestone com a data final calculada;
- inclui no corpo de cada issue a data prevista de início e fim conforme o milestone;
- ao usar Project v2, cria/usa campos de data e preenche as datas dos itens para visualização no Roadmap.

As durações dos milestones e os campos usados no Project podem ser configurados no `backlog_github_project.json`:

```json
{
  "schedule": {
    "project_start_date": "2026-05-01",
    "project_date_fields": {
      "start": "Início previsto",
      "end": "Fim previsto"
    },
    "milestone_durations": {
      "M1": {"value": 15, "unit": "days"},
      "M2": {"value": 1, "unit": "months"},
      "M3": {"value": 3, "unit": "months"},
      "M4": {"value": 1, "unit": "months"},
      "M5": {"value": 15, "unit": "days"}
    }
  },
  "milestones": [
    {"key": "M1", "title": "M1 - Exploração"},
    {"key": "M2", "title": "M2 - Viabilidade e Concepção"}
  ]
}
```

Com essa configuração, todas as issues de um milestone recebem a mesma janela prevista:

- issues de `M1`: início na data inicial do projeto e fim no prazo calculado para `M1`;
- issues de `M2`: início no dia seguinte ao fim de `M1` e fim após a duração prevista de `M2`;
- e assim sucessivamente até `M5`.

### 3) Criar também um Project v2 vinculado ao repositório

```bash
export GITHUB_TOKEN=<SEU_TOKEN>
python3 scripts/roadmap_builder.py --owner <OWNER_REPO> --repo <NOME_REPO> --apply --create-project --project-title "RoadmapBuilder"
```

O GitHub Projects v2 exige que o Project seja criado sob um owner (`User` ou `Organization`). Depois de criar o Project, o script o vincula ao repositório com `linkProjectV2ToRepository`, para que ele fique associado ao repo em vez de ficar solto apenas na conta do usuário.

### 4) Usar um Project v2 já existente e vinculá-lo ao repositório

```bash
export GITHUB_TOKEN=<SEU_TOKEN>
python3 scripts/roadmap_builder.py --owner <OWNER_REPO> --repo <NOME_REPO> --apply --project-number <NUMERO_PROJECT>
```

### Permissões necessárias do token (`GITHUB_TOKEN`)

Para automações que criam/atualizam **milestones**, **issues** e **Project v2** via API do GitHub, use um token com as permissões abaixo.

#### Fine-grained Personal Access Token (recomendado)

- **Repository permissions**
  - `Issues: Read and write`
  - `Metadata: Read-only`
- **Account/Organization permissions** (quando houver operação com Project v2)
  - `Projects: Read and write`

#### Classic Personal Access Token

- `repo` (repositórios privados)
- `project` (Project v2)
- `read:org` (se o repositório pertencer a uma organização)

> Observações:
> - Se a organização usa SSO/SAML, é necessário autorizar o token na organização.
> - Se não for manipular Project v2, a permissão de `Projects` não é necessária.
> - Se o token tiver apenas `repo` e `workflow`, consultas de organização no GraphQL podem falhar com `INSUFFICIENT_SCOPES`.
