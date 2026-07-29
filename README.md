# Typographic Story Engine

Motor experimental para reconstruir objetos usando somente letras semanticamente permitidas. Um objeto `MOON`, por exemplo, usa apenas `M`, `O`, `O`, `N`; letras repetidas continuam influenciando a frequência de amostragem.

## Renderer v0.1

A versão atual recebe uma máscara raster e gera uma composição determinística em SVG estrito. O pipeline combina:

1. distância exata até a borda;
2. distribuição espacial controlada;
3. orientação adaptativa pela curvatura;
4. camadas tipográficas independentes;
5. papéis visuais para contorno, preenchimento e textura;
6. validação semântica e estrutural.

Cada glyph registra posição, tamanho, rotação, opacidade, cor, profundidade, zona, camada, papel visual e métricas de orientação.

## Renderer oficial: `balanced`

O modo padrão combina o contorno orgânico com um preenchimento espacialmente controlado:

- `outline_detail`: define a silhueta com letras pequenas e orientadas;
- `outline_shadow`: cria profundidade com uma faixa interna mais suave;
- `fill_mass`: preenche a forma sem clusters escuros;
- `texture_accent`: acrescenta detalhe leve e distribuído.

Os renderers anteriores continuam disponíveis para comparação:

```text
balanced  # padrão de produção
organic   # contorno e preenchimento com modulação orgânica mais forte
layered   # outline, fill e texture independentes
legacy    # distribuição por edge, mid e core
```

## Estrutura do SVG

A arte visível é formada somente por `<text>`. Elementos `<g>` são usados exclusivamente para organização e transformação:

```text
layer_texture
  role_texture_accent
layer_fill
  role_fill_mass
layer_outline
  role_outline_shadow
  role_outline_detail
```

Cada `<text>` possui:

```text
data-glyph-id
data-object-id
data-layer
data-zone
data-style-role
```

Essa estrutura permite animar objetos e subcamadas sem converter a arte em formas geométricas.

## Instalação no Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Confirme o ambiente ativo:

```powershell
python -c "import sys; print(sys.executable)"
```

O caminho deve terminar em:

```text
typographic-story-engine\venv\Scripts\python.exe
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

Como `balanced` é o padrão, não é necessário informar `--layer-mode`.

Para comparar outro renderer:

```powershell
--layer-mode organic
--layer-mode layered
--layer-mode legacy
```

O comando antigo continua válido como wrapper de compatibilidade:

```powershell
python render_balanced_from_mask.py ...
```

## Artefatos gerados

```text
<id>_scene.svg
<id>_scene.json
<id>_validation.json
<id>_preview.png
```

O relatório inclui:

- versão e modo do renderer;
- seed e sequência semântica;
- contagem por zona, camada e papel;
- métricas de orientação;
- métricas de concentração local do renderer balanceado;
- letras inválidas e tags proibidas.

## Validação

```powershell
python -m pytest -q
```

A suíte cobre determinismo, letras repetidas, ocupação espacial, orientação, camadas, papéis visuais, ausência de formas proibidas e leitura de máscaras.

## Próximo marco: end-to-end v0

O próximo objetivo é provar o produto completo com o menor caminho possível:

```text
história curta
  → Scene Graph
  → cena com vários objetos
  → duas cenas persistentes
  → animação por grupos SVG
  → frames PNG
  → MP4
  → endpoint FastAPI
```

A primeira demonstração usará três objetos semânticos independentes:

```text
CAT + MOON + GROUND
```

Cada objeto terá máscara, palavra, seed, posição, escala, rotação e `z_index` próprios. O primeiro vídeo animará grupos inteiros; morphing individual de glyphs será desenvolvido somente depois que o pipeline completo estiver funcionando.
