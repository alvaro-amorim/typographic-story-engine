# Typographic Story Engine

Motor local para transformar histórias curtas em cenas e vídeos compostos por letras semanticamente permitidas.

Um objeto `MOON`, por exemplo, usa somente `M`, `O`, `O`, `N`. Um objeto `CAT` usa somente `C`, `A`, `T`. Cada objeto mantém sua própria regra mesmo quando vários deles aparecem na mesma cena.

## Estado atual — end-to-end v0.2

O projeto já executa o fluxo:

```text
história curta
  → Asset Registry
  → planejamento determinístico ou Ollama local
  → dois Scene Graphs persistentes
  → composição multiobjeto
  → animação por grupos SVG
  → frames SVG/PNG
  → MP4 com FFmpeg
  → jobs pela FastAPI local
```

O renderer individual continua sendo SVG estrito: toda arte visível é formada por `<text>`. Elementos `<g>` são usados somente para organização, transformação e animação.

## Principais módulos

### Renderer `balanced`

Recebe uma máscara raster e produz glyphs determinísticos com:

- distância exata até a borda;
- distribuição espacial controlada;
- orientação pela curvatura;
- camadas `outline`, `fill` e `texture`;
- papéis `outline_detail`, `outline_shadow`, `fill_mass` e `texture_accent`;
- validação semântica e estrutural.

### Scene Composer

Combina objetos já renderizados sem regenerar glyphs. Cada objeto possui:

- ID persistente;
- palavra semântica;
- posição;
- escala;
- rotação;
- opacidade;
- visibilidade;
- `z_index`.

### Object Animation

Interpola duas cenas que compartilham os mesmos objetos e glyphs:

- `x` e `y`;
- `scale_x` e `scale_y`;
- rotação pelo caminho angular mais curto;
- opacidade e fade;
- easing;
- duração e FPS.

### Story Planner

O planner determinístico entende aliases em inglês e português e gera duas cenas compatíveis.

O provider Ollama é opcional e usa structured output com JSON Schema. O modelo escolhe somente assets existentes; ele não gera SVG nem coordenadas de glyphs. Em caso de erro, o sistema pode retornar ao planner determinístico.

### FastAPI local

A API oferece jobs em background, progresso, persistência local e download seguro de artefatos.

## Instalação no Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Confirme o ambiente:

```powershell
python -c "import sys; print(sys.executable)"
```

## Gerar um objeto

```powershell
python render_object_from_mask.py `
  --id moon_01 `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon
```

O renderer `balanced` é o padrão. Os modos `organic`, `layered` e `legacy` continuam disponíveis para comparação.

## Primeiro demo multiobjeto

```powershell
python -m examples.build_cat_moon_ground_demo
```

Cena:

```text
CAT + MOON + GROUND
```

## Gerar frames de animação

```powershell
python -m examples.build_cat_walk_animation_demo `
  --duration 1 `
  --fps 4 `
  --skip-png
```

## Gerar o primeiro MP4

Requer FFmpeg disponível no `PATH`:

```powershell
ffmpeg -version
```

Depois:

```powershell
python -m examples.build_cat_walk_video_demo `
  --duration 1 `
  --fps 6 `
  --preset fast
```

Saída:

```text
outputs/demo-cat-walk-video/cat_walk_01.mp4
```

## História para vídeo

Sem FFmpeg:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 1 `
  --fps 4 `
  --skip-video
```

Com MP4:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 2 `
  --fps 12 `
  --preset fast
```

## Usar Ollama local

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

O fallback determinístico é ativado por padrão. Use `--no-fallback` para testar exclusivamente o modelo.

## Executar a API

```powershell
python run_api.py --reload
```

OpenAPI e interface interativa:

```text
http://127.0.0.1:8000/docs
```

Endpoints:

```text
GET  /health
POST /v1/jobs
GET  /v1/jobs
GET  /v1/jobs/{job_id}
GET  /v1/jobs/{job_id}/artifacts
GET  /v1/jobs/{job_id}/artifacts/{artifact_path}
```

## Estrutura dos artefatos

```text
plans/
  <story>_plan.json
  <story>_scene_001.json
  <story>_scene_002.json
  <story>_animation.json
animation/
  <transition>/
    <transition>_manifest.json
    <transition>_validation.json
    frames/svg/
    frames/png/
<story>.mp4
```

## Validação

```powershell
python -m pytest -q
```

A suíte cobre:

- determinismo e letras repetidas;
- distribuição, curvatura e camadas;
- SVG sem formas visíveis proibidas;
- semântica separada por objeto;
- Scene Graph e `z_index`;
- persistência dos glyphs entre frames;
- easing e interpolação;
- exportação FFmpeg simulada no CI;
- Asset Registry e planner;
- structured output do Ollama;
- fallback determinístico;
- pipeline completo;
- jobs e artefatos da FastAPI.

O CI executa a suíte no Windows com Python 3.12 e 3.14.

## Documentação técnica

- `docs/SCENE_COMPOSER.md`
- `docs/OBJECT_ANIMATION.md`
- `docs/VIDEO_EXPORT.md`
- `docs/STORY_PLANNER.md`
- `docs/OLLAMA_PLANNER.md`
- `docs/LOCAL_API.md`

## Limites atuais

- o Asset Registry de demonstração ainda possui poucos objetos;
- a animação move grupos completos, não glyphs individuais;
- o planner produz duas cenas por história;
- `BackgroundTasks` é adequado ao MVP local, não a uma fila distribuída;
- FFmpeg e Ollama são dependências externas opcionais.

## Próximos marcos

1. ampliar o catálogo de personagens, poses e cenários;
2. suportar histórias com várias cenas e transições;
3. adicionar matching e morphing individual de glyphs;
4. criar uma fila de workers para produção;
5. adicionar armazenamento persistente e autenticação à API;
6. criar editor visual e interface web.
