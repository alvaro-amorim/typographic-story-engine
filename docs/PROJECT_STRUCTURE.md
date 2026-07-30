# Project structure

A organização oficial do repositório é:

```text
typographic-story-engine/
├── api_server/          # FastAPI, jobs e persistência local
├── assets/              # referências visuais aprovadas e licenças
├── commands/            # comandos oficiais executados com python -m
├── docs/                # documentação técnica por módulo
├── engine/              # lógica de domínio e renderização
├── examples/            # demos reproduzíveis de ponta a ponta
├── outputs/             # artefatos descartáveis; deve começar vazio
├── tests/               # suíte automatizada
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Responsabilidade de cada pasta

### `engine/`

Código reutilizável. Não deve depender de argumentos de terminal nem de FastAPI. Novos algoritmos, modelos Pydantic, validadores, renderers e serviços pertencem aqui.

### `commands/`

Entrada oficial para usuários e automações:

```powershell
python -m commands.render_object
python -m commands.render_scene
python -m commands.animate
python -m commands.export_video
python -m commands.plan_story
python -m commands.run_api
python -m commands.build_assets
python -m commands.clean_outputs
```

Os scripts antigos na raiz permanecem temporariamente como compatibilidade, mas novos exemplos e documentos devem usar `commands/`.

### `assets/`

Somente referências aprovadas e versionadas. Cada asset deve possuir:

- `source.svg` em preto e branco;
- `metadata.json` com licença e origem;
- entrada em `assets/catalog.json`;
- anchors normalizados quando relevantes.

Máscaras PNG derivadas não são versionadas. Elas são reconstruídas em `outputs/_asset_cache/`.

### `examples/`

Demos completas e reproduzíveis. Demos não devem esconder lógica de produção nem criar referências visuais improvisadas. Elas devem consumir `engine/`, `commands/` e `assets/`.

### `outputs/`

Área descartável. Não contém fonte do projeto e pode ser apagada integralmente:

```powershell
python -m commands.clean_outputs
```

### `api_server/`

Somente camada HTTP, modelos de job e armazenamento local de status. A lógica do pipeline permanece em `engine/`.

## Regras para novos arquivos

1. Evitar novos scripts na raiz.
2. Lógica reutilizável entra em `engine/`.
3. CLIs entram em `commands/`.
4. Demos entram em `examples/`.
5. Referências visuais entram em `assets/` com licença.
6. Arquivos gerados entram exclusivamente em `outputs/`.
7. Cada módulo novo deve possuir testes em `tests/` e documentação em `docs/` quando necessário.
