# Typographic Story Engine

Motor experimental para reconstruir objetos usando apenas glyphs semanticamente permitidos. Um objeto `MOON`, por exemplo, só pode usar `M`, `O`, `O`, `N`; a repetição do `O` também influencia a frequência de amostragem.

## Estado atual

O MVP recebe uma máscara raster e gera uma composição determinística em SVG estrito. O pipeline combina:

1. distância exata até a borda;
2. distribuição espacial sem aglomeração excessiva;
3. orientação adaptativa pela curvatura local;
4. renderer tipográfico em camadas.

Cada glyph registra posição, tamanho, rotação, opacidade, cor, profundidade, zona, camada e métricas de orientação.

## Camadas tipográficas

O modo padrão é `layered`. Ele separa três responsabilidades visuais:

- `outline`: desenha os contornos externo e interno com letras menores, mais opacas e fortemente orientadas;
- `fill`: constrói a massa do objeto com densidade e orientação moderadas;
- `texture`: adiciona riqueza interna com baixa opacidade e pouca influência estrutural.

A divisão padrão para 8.000 glyphs é:

- `outline`: 2.800 glyphs — 35%;
- `fill`: 4.000 glyphs — 50%;
- `texture`: 1.200 glyphs — 15%.

O SVG agrupa os elementos em:

```text
layer_texture
layer_fill
layer_outline
```

Cada `<text>` possui `data-glyph-id`, `data-object-id`, `data-layer` e `data-zone`. Essa estrutura prepara o arquivo para animações e correspondência de glyphs entre cenas.

## Artefatos gerados

- SVG estrito composto apenas por `<text>` e grupos organizacionais;
- JSON com o estado completo de cada glyph;
- relatório de validação semântica, distribuição e métricas por camada;
- prévia PNG.

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

## Testar o renderer em camadas

```powershell
git fetch origin
git switch agent/layered-typographic-renderer
git pull origin agent/layered-typographic-renderer
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Gere a lua:

```powershell
python render_object_from_mask.py `
  --id moon_layered `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-layered
```

O terminal deve registrar aproximadamente:

```text
Camadas: outline=2800, fill=4000, texture=1200
```

Para comparar com o renderer anterior:

```powershell
python render_object_from_mask.py `
  --id moon_legacy `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --layer-mode legacy `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-legacy
```

## Controles de camada

- `--layer-mode layered|legacy`: alterna entre o novo renderer e o comportamento anterior;
- `--outline-ratio`: orçamento do contorno; padrão `0.35`;
- `--fill-ratio`: orçamento do preenchimento; padrão `0.50`;
- `--texture-ratio`: orçamento da textura; padrão `0.15`;
- `--outline-depth-max`: largura da faixa de contorno; padrão `0.18`;
- `--fill-depth-min`: profundidade mínima do preenchimento; padrão `0.035`;
- `--texture-depth-min`: profundidade mínima da textura; padrão `0.20`.

Os valores de proporção são normalizados automaticamente e sempre preservam o total exato de glyphs.

## Orientação adaptativa

A orientação continua dependente de zona, profundidade e confiança local:

- `edge`: força máxima `0.90`;
- `mid`: força máxima `0.48`;
- `core`: força máxima `0.12`.

Cada camada multiplica essas forças:

- `outline`: `1.00`;
- `fill`: `0.45`;
- `texture`: `0.08`.

Assim, o contorno acompanha a forma, o preenchimento mantém fluxo moderado e a textura permanece orgânica.

## Validação

```powershell
python -m pytest -q
```

A suíte cobre:

- determinismo por seed;
- frequência de letras repetidas;
- distribuição exata por zonas e camadas;
- ocupação espacial;
- orientação adaptativa;
- responsabilidades visuais distintas entre `outline`, `fill` e `texture`;
- ordem de pintura do SVG;
- ausência de formas proibidas;
- leitura e validação de máscaras.

## Próximo marco

Depois da validação visual do renderer em camadas, o próximo passo será gerar uma cena com vários objetos semânticos e compor cada objeto em um grupo independente, preparando transições entre dois SVGs.
