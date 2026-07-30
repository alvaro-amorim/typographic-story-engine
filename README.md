# Typographic Story Engine

Motor local para transformar histórias curtas em cenas e vídeos compostos por letras semanticamente permitidas.

Um objeto `MOON` usa somente `M`, `O`, `O`, `N`. Um objeto `CAT` usa somente `C`, `A`, `T`. Cada objeto mantém sua regra mesmo quando vários deles aparecem na mesma cena.

## Estado atual — end-to-end v0.2.1

```text
história curta
  → Asset Registry
  → planner determinístico ou Ollama local
  → Scene Graphs persistentes
  → composição multiobjeto
  → animação por grupos SVG
  → frames SVG/PNG
  → MP4 com FFmpeg
  → jobs pela FastAPI local
```

A arte final continua sendo SVG estrito: toda parte visível é `<text>`. Grupos `<g>` são usados somente para organização e transformação.

## Estrutura do repositório

```text
├── api_server/   # FastAPI e jobs locais
├── assets/       # silhuetas aprovadas, metadados e licenças
├── commands/     # CLIs oficiais executadas com python -m
├── docs/         # documentação técnica
├── engine/       # lógica reutilizável do produto
├── examples/     # demonstrações reproduzíveis
├── outputs/      # artefatos descartáveis; começa vazio
└── tests/        # suíte automatizada
```

Consulte `docs/PROJECT_STRUCTURE.md` antes de adicionar novos arquivos.

## Instalação no Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Limpar todas as gerações anteriores

`outputs/` não contém fonte do projeto. Para apagar todo o seu conteúdo local e começar uma nova rodada:

```powershell
python -m commands.clean_outputs
```

O comando possui proteção para não apagar diretórios fora do repositório.

## Biblioteca de silhuetas

As referências visuais ficam em `assets/`. O demo não desenha mais um gato provisório com primitivas do Pillow.

Assets iniciais:

```text
cat_standing_side_01
cat_sitting_side_01
cat_walking_side_01
moon_crescent_01
ground_hill_01
```

Cada asset possui:

- `source.svg` preto e branco;
- `metadata.json` com autoria e licença;
- entrada em `assets/catalog.json`;
- anchors normalizados para uso futuro em articulação.

Construa as máscaras PNG derivadas:

```powershell
python -m commands.build_assets
```

Saída:

```text
outputs/_asset_cache/<category>/<subject>/<asset-id>/mask.png
```

As máscaras derivadas não são versionadas; podem ser reconstruídas a qualquer momento.

## Comandos oficiais

```powershell
python -m commands.render_object --help
python -m commands.render_scene --help
python -m commands.animate --help
python -m commands.export_video --help
python -m commands.plan_story --help
python -m commands.run_api --help
python -m commands.build_assets --help
python -m commands.clean_outputs --help
```

Os scripts antigos da raiz permanecem temporariamente como compatibilidade, mas novas instruções devem usar `commands/`.

## Gerar um objeto

```powershell
python -m commands.render_object `
  --id moon_01 `
  --word MOON `
  --mask outputs/_asset_cache/environment/moon/moon_crescent_01/mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon
```

O renderer `balanced` é o padrão. Os modos `organic`, `layered` e `legacy` continuam disponíveis para comparação.

## Demo multiobjeto com assets aprovados

```powershell
python -m examples.build_cat_moon_ground_demo --clean
```

A cena usa:

```text
CAT + MOON + GROUND
```

Para trocar a pose do gato:

```powershell
python -m examples.build_cat_moon_ground_demo `
  --clean `
  --cat-asset cat_sitting_side_01
```

O demo grava `asset_provenance.json`, relacionando cada objeto ao asset de referência utilizado.

## História para frames

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 1 `
  --fps 4 `
  --skip-video
```

## História para MP4

Requer FFmpeg no `PATH`:

```powershell
ffmpeg -version
```

Depois:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 2 `
  --fps 12 `
  --preset fast
```

## Planner com Ollama local

```powershell
ollama pull qwen3:4b
```

```powershell
python -m examples.build_story_video_demo `
  --story "O gato olha para a lua e caminha para a esquerda." `
  --provider ollama `
  --ollama-model qwen3:4b `
  --skip-video
```

O modelo seleciona apenas assets existentes. Ele não cria silhuetas, SVGs ou glyphs arbitrários. O fallback determinístico permanece ativado por padrão.

## API local

```powershell
python -m commands.run_api --reload
```

Documentação interativa:

```text
http://127.0.0.1:8000/docs
```

Endpoints principais:

```text
GET  /health
POST /v1/jobs
GET  /v1/jobs
GET  /v1/jobs/{job_id}
GET  /v1/jobs/{job_id}/artifacts
GET  /v1/jobs/{job_id}/artifacts/{artifact_path}
```

## Validação

```powershell
python -m pytest -q
```

O CI executa a suíte no Windows com Python 3.12 e Python 3.14.

## Documentação técnica

- `docs/PROJECT_STRUCTURE.md`
- `docs/SCENE_COMPOSER.md`
- `docs/OBJECT_ANIMATION.md`
- `docs/VIDEO_EXPORT.md`
- `docs/STORY_PLANNER.md`
- `docs/OLLAMA_PLANNER.md`
- `docs/LOCAL_API.md`
- `assets/README.md`

## Próximos marcos

1. validar visualmente as novas silhuetas aprovadas;
2. associar poses e anchors ao Asset Registry narrativo;
3. criar personagens compostos por partes semânticas;
4. implementar movimentos `idle`, `look_at`, `turn` e `walk`;
5. evoluir de duas cenas para uma timeline arbitrária;
6. adicionar morphing individual de glyphs.
