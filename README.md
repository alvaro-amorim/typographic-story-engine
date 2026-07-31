# Typographic Story Engine

Motor local para transformar histórias curtas em cenas e vídeos compostos por letras semanticamente permitidas.

Um objeto `MOON` usa somente `M`, `O`, `O`, `N`. Um objeto `CAT` usa somente `C`, `A`, `T`. Cada objeto mantém sua própria regra semântica mesmo quando vários aparecem na mesma cena.

## Estado atual — Prompt Video Studio v0.3

```text
prompt
  → Asset Registry aprovado
  → planner determinístico ou Ollama local
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
- acompanhar o progresso;
- assistir ao MP4 na própria página;
- abrir os manifests e relatórios;
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

O comando verifica Python, dependências, catálogo, FFmpeg, registry do Studio e Ollama.

## Instalação no Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Estrutura do repositório

```text
├── api_server/   # FastAPI, Studio web e jobs locais
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

Baseline atual:

```text
cat_sitting_side_01   # contemplativo
cat_walking_side_01   # locomoção
cat_standing_side_01  # neutro auxiliar
moon_crescent_01
ground_hill_01
```

Cada asset possui:

- `source.svg` em preto e branco;
- `metadata.json` com autoria e licença;
- entrada em `assets/catalog.json`;
- anchors normalizados para articulação futura.

Construa as máscaras PNG derivadas:

```powershell
python -m commands.build_assets
```

Saída:

```text
outputs/_asset_cache/<category>/<subject>/<asset-id>/mask.png
```

## API simplificada por prompt

```http
POST /v1/generations
Content-Type: application/json
```

```json
{
  "prompt": "A cat looks at the moon and then walks away.",
  "provider": "deterministic",
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

A API avançada continua disponível para enviar um `StoryPipelineRequest` completo:

```text
GET    /health
GET    /v1/capabilities
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

Cena contemplativa com assets aprovados:

```powershell
python -m examples.build_cat_moon_ground_demo --clean
```

História para frames:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 1 `
  --fps 4 `
  --skip-video
```

História para MP4:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 2 `
  --fps 12 `
  --preset fast
```

## Ollama local

```powershell
ollama pull qwen3:4b
```

No Studio, selecione `Ollama local`, ou use:

```powershell
python -m examples.build_story_video_demo `
  --story "O gato olha para a lua e caminha para a esquerda." `
  --provider ollama `
  --ollama-model qwen3:4b `
  --skip-video
```

O modelo seleciona apenas assets existentes. Ele não cria silhuetas, SVGs ou glyphs arbitrários. O fallback determinístico permanece ativado por padrão.

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

- o catálogo narrativo ainda está centrado em `CAT`, `MOON` e `GROUND`;
- cada história gera duas cenas;
- a transição real `sitting → walking` ainda está planejada;
- a animação atual move grupos completos;
- os jobs usam `BackgroundTasks` no mesmo processo;
- FFmpeg é obrigatório para MP4;
- Ollama é opcional.

## Próximos marcos

1. transição persistente entre poses aprovadas;
2. personagens compostos por partes semânticas;
3. movimentos `idle`, `look_at`, `turn` e `walk`;
4. timeline com número arbitrário de cenas;
5. fila de workers para geração concorrente;
6. morphing individual de glyphs.
