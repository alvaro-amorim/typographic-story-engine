# Typographic Story Engine

Motor local para transformar histórias curtas em cenas e vídeos compostos por letras semanticamente permitidas.

Um objeto `MOON` usa somente `M`, `O`, `O`, `N`. Um objeto `CAT` usa somente `C`, `A`, `T`. Cada objeto mantém sua própria regra semântica mesmo quando vários aparecem na mesma cena.

## Estado atual — Prompt Video Studio v0.5

```text
prompt
  → Asset Registry aprovado
  → planner determinístico ou Ollama local descoberto automaticamente
  → relações espaciais medidas
  → orientação coerente do personagem
  → Scene Graphs persistentes
  → composição multiobjeto
  → animação por grupos SVG
  → frames SVG/PNG
  → MP4 com FFmpeg
  → player no navegador
```

A arte continua sendo SVG estrito: toda parte visível é `<text>`. Grupos `<g>` são usados somente para organização e transformação.

## Início mais rápido

Com o ambiente virtual ativo:

```powershell
python -m commands.studio
```

O comando prepara o registry padrão quando necessário, inicia a API e abre:

```text
http://127.0.0.1:8000/studio
```

No Studio você pode:

- escrever o prompt do vídeo;
- escolher modo rápido, padrão ou qualidade;
- usar planner determinístico ou Ollama;
- descobrir e selecionar modelos Ollama instalados;
- testar uma inferência local e medir sua latência;
- ver claramente quando o fallback determinístico foi usado;
- navegar pelos assets disponíveis;
- acompanhar o progresso;
- assistir ao MP4 na própria página;
- abrir manifests e relatórios;
- excluir testes antigos.

Para desenvolvimento com reload:

```powershell
python -m commands.studio --reload
```

Launcher PowerShell opcional:

```powershell
.\scripts\start-studio.ps1 -Reload
```

## Diagnóstico automático

```powershell
python -m commands.doctor --prepare-assets
```

O comando verifica Python, dependências, catálogo, FFmpeg, registry do Studio, versão do Ollama, latência e nomes dos modelos locais.

## Instalação no Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Estrutura do repositório

```text
├── api_server/   # FastAPI, Studio web, Ollama local e jobs
├── assets/       # silhuetas aprovadas, metadados e licenças
├── commands/     # CLIs oficiais executadas com python -m
├── docs/         # documentação técnica
├── engine/       # lógica reutilizável do produto
├── examples/     # demonstrações reproduzíveis
├── outputs/      # artefatos descartáveis; começa vazio
├── scripts/      # atalhos de desenvolvimento para Windows
└── tests/        # suíte automatizada
```

Consulte `docs/PROJECT_STRUCTURE.md` antes de adicionar novos arquivos.

## Limpar todas as gerações

```powershell
python -m commands.clean_outputs
```

`outputs/` não contém código-fonte. O comando possui proteção contra remoção de diretórios externos ao repositório.

## Biblioteca de silhuetas

As referências visuais ficam em `assets/`.

Catálogo narrativo atual:

```text
CAT     # sitting, standing e walking
BIRD    # flying
MOON
GROUND
STAR
CLOUD
SUN
TREE
```

Cada asset possui:

- `source.svg` em preto e branco;
- `metadata.json` com autoria e licença;
- entrada em `assets/catalog.json`;
- anchors normalizados para articulação futura;
- orientação de origem (`facing`) quando é um personagem lateral.

Construa as máscaras PNG derivadas:

```powershell
python -m commands.build_assets
```

Saída:

```text
outputs/_asset_cache/<category>/<subject>/<asset-id>/mask.png
```

## Composição espacial

O planner determinístico reconhece relações explícitas em português e inglês:

```text
above / acima de
below / under / sob / abaixo de
near / beside / perto de / ao lado de
left of / à esquerda de
right of / à direita de
```

A posição é calculada a partir dos limites reais dos glyphs de cada asset, e não apenas por coordenadas fixas.

Exemplos:

```text
A bird flies above a cloud under the moon.
Um pássaro voa acima de uma nuvem sob a lua.
A cat walks near a tree under the stars.
A bird flies to the right of a cloud.
```

Relações encadeadas são aplicadas em mais de uma passagem para que objetos dependentes acompanhem o reposicionamento da referência.

## Direção visual dos personagens

`CAT` e `BIRD` declaram para qual lado a silhueta original olha. Quando o movimento ocorre no sentido oposto, o compositor reflete as posições e rotações dos glyphs individualmente.

Isso evita o efeito de “andar de ré” sem usar `scale(-1)`: as letras continuam normais e legíveis.

## Ollama local

Instale um modelo, por exemplo:

```powershell
ollama pull qwen3:4b
```

No Studio:

1. selecione `Ollama local`;
2. escolha um modelo encontrado automaticamente;
3. clique em `Testar modelo`;
4. confirme o tempo da inferência;
5. gere o vídeo.

O Studio consulta a versão e os modelos instalados, preserva URL/modelo/timeout no navegador e mostra separadamente o planner solicitado e o planner efetivo.

O modelo ainda seleciona apenas assets existentes. A validação e a aplicação espacial permanecem sob controle do motor local. O fallback determinístico continua ativado por padrão, mas pode ser desligado para avaliar falhas reais do modelo.

## API simplificada por prompt

```http
POST /v1/generations
Content-Type: application/json
```

```json
{
  "prompt": "A bird flies left above a cloud under the moon.",
  "provider": "ollama",
  "ollama_model": "qwen3:4b",
  "ollama_url": "http://localhost:11434",
  "ollama_timeout": 60,
  "fallback_to_deterministic": true,
  "preset": "draft",
  "generate_video": true
}
```

Presets disponíveis:

```text
draft     # 1s, 6 FPS, ultrafast
standard  # 2s, 12 FPS, veryfast
quality   # 4s, 24 FPS, medium
```

Consulte `docs/PROMPT_STUDIO.md` para o contrato completo.

## API técnica

```text
GET    /health
GET    /v1/capabilities
GET    /v1/ollama/status
POST   /v1/ollama/test
POST   /v1/generations
POST   /v1/jobs
GET    /v1/jobs
GET    /v1/jobs/{job_id}
DELETE /v1/jobs/{job_id}
GET    /v1/jobs/{job_id}/preview
GET    /v1/jobs/{job_id}/video
GET    /v1/jobs/{job_id}/artifacts
GET    /v1/jobs/{job_id}/artifacts/{artifact_path}
```

`GET /v1/capabilities` informa:

- assets e aliases ativos;
- relações espaciais suportadas;
- disponibilidade de FFmpeg;
- suporte a orientação automática e espelhamento legível;
- endpoints e suporte de fallback do Ollama.

OpenAPI:

```text
http://127.0.0.1:8000/docs
```

## Comandos oficiais

```powershell
python -m commands.studio --help
python -m commands.doctor --help
python -m commands.render_object --help
python -m commands.render_scene --help
python -m commands.animate --help
python -m commands.export_video --help
python -m commands.plan_story --help
python -m commands.run_api --help
python -m commands.build_assets --help
python -m commands.clean_outputs --help
```

## Demos reproduzíveis

Cena contemplativa:

```powershell
python -m examples.build_cat_moon_ground_demo --clean
```

História para frames:

```powershell
python -m examples.build_story_video_demo `
  --story "A bird flies left above a cloud under the moon." `
  --duration 1 `
  --fps 4 `
  --skip-video
```

História para MP4:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat walks near a tree under the stars." `
  --duration 2 `
  --fps 12 `
  --preset fast
```

## Validação

```powershell
python -m pytest -q
```

O CI executa a suíte no Windows com Python 3.12 e Python 3.14.

## Documentação técnica

- `docs/PROMPT_STUDIO.md`
- `docs/PROJECT_STRUCTURE.md`
- `docs/SCENE_COMPOSER.md`
- `docs/OBJECT_ANIMATION.md`
- `docs/VIDEO_EXPORT.md`
- `docs/STORY_PLANNER.md`
- `docs/OLLAMA_PLANNER.md`
- `docs/LOCAL_API.md`
- `assets/README.md`

## Limites atuais

- o Ollama ainda seleciona somente assets existentes;
- cada história ainda gera duas cenas;
- a transição real `sitting → walking` ainda está planejada;
- a animação atual move grupos completos;
- as relações espaciais são binárias e explícitas;
- múltiplas instâncias da mesma palavra ainda não possuem IDs narrativos separados;
- os jobs usam `BackgroundTasks` no mesmo processo;
- FFmpeg é obrigatório para MP4;
- Ollama é opcional.

## Próximos marcos

1. storyboard Ollama com várias cenas, objetos, ações e durações;
2. validação e reparo automático do plano;
3. Asset Resolver para conceitos ausentes;
4. animação interna das letras;
5. timeline com várias ações e cenas;
6. transição persistente entre poses aprovadas;
7. fila de workers para geração concorrente.
