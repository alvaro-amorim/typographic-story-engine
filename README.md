# Typographic Story Engine

Motor experimental para reconstruir objetos usando apenas glyphs semanticamente permitidos. Um objeto `MOON`, por exemplo, só pode usar `M`, `O`, `O`, `N`; a repetição do `O` também influencia a frequência de amostragem.

## Estado atual

O MVP recebe uma máscara raster e gera uma composição determinística em SVG estrito. O pipeline combina:

1. distância exata até a borda;
2. distribuição espacial sem aglomeração excessiva;
3. orientação adaptativa pela curvatura local;
4. camadas tipográficas independentes;
5. direção artística orgânica por subcamadas.

Cada glyph registra posição, tamanho, rotação, opacidade, cor, profundidade, zona, camada, papel visual e métricas de orientação.

## Modo orgânico

O modo padrão agora é `organic`. Ele mantém as três camadas principais, mas divide suas responsabilidades em quatro papéis visuais:

- `outline_detail`: letras menores, mais precisas e fortemente orientadas para desenhar a silhueta final;
- `outline_shadow`: faixa mais interna, maior e menos opaca, que dá profundidade sem criar um traço uniforme;
- `fill_mass`: preenchimento com contraste e variação de tamanho maiores, mas orientação estrutural reduzida;
- `texture_accent`: menos glyphs, opacidade perceptível e rotação livre para enriquecer o interior.

A divisão padrão para 8.000 glyphs é:

- `outline`: 2.720 glyphs — 34%;
- `fill`: 4.320 glyphs — 54%;
- `texture`: 960 glyphs — 12%.

Dentro do orçamento de contorno, 32% formam `outline_shadow` e 68% formam `outline_detail`.

## Espessura orgânica

O contorno não recebe mais a mesma densidade em toda a curva. Um campo determinístico de baixa frequência modula:

- seleção de posições;
- tamanho dos glyphs;
- opacidade;
- contraste da paleta;
- presença relativa de sombra e detalhe.

A mesma seed continua produzindo exatamente o mesmo resultado, mas a borda deixa de parecer uma faixa mecânica.

## Estrutura do SVG

O SVG continua usando somente `<text>` para a arte. Os glyphs são agrupados em:

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

Essa estrutura já permite animar subcamadas separadamente e manter correspondência entre glyphs em cenas futuras.

## Artefatos gerados

- SVG estrito composto apenas por `<text>` e grupos organizacionais;
- JSON com o estado completo de cada glyph;
- relatório de validação semântica e métricas por zona, camada e papel visual;
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

## Testar o estilo orgânico

```powershell
git fetch origin
git switch agent/organic-layer-styling
git pull origin agent/organic-layer-styling
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Gere a lua:

```powershell
python render_object_from_mask.py `
  --id moon_organic `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-organic
```

O terminal deve registrar aproximadamente:

```text
Camadas: outline=2720, fill=4320, texture=960
Papéis orgânicos: outline_shadow=870, outline_detail=1850, fill_mass=4320, texture_accent=960
```

## Comparar com o modo layered

```powershell
python render_object_from_mask.py `
  --id moon_layered `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --layer-mode layered `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-layered-comparison
```

O modo `legacy` também permanece disponível:

```powershell
--layer-mode legacy
```

## Controles orgânicos

- `--layer-mode organic|layered|legacy`: seleciona o renderer;
- `--outline-ratio`, `--fill-ratio`, `--texture-ratio`: orçamento das camadas;
- `--outline-shadow-fraction`: parcela do contorno usada pela sombra interna; padrão `0.32`;
- `--outline-detail-depth-max`: largura da faixa de detalhe; padrão `0.105`;
- `--outline-shadow-depth-min`: início da sombra interna; padrão `0.045`;
- `--outline-depth-max`: limite interno total do contorno; padrão `0.18`;
- `--organic-scale`: escala espacial da modulação; padrão `0.032`;
- `--texture-opacity-min`: opacidade mínima da textura; padrão `0.20`;
- `--texture-opacity-max`: opacidade máxima da textura; padrão `0.31`.

As proporções são normalizadas automaticamente e sempre preservam o total exato de glyphs.

## Orientação por papel

A orientação adaptativa continua dependente de zona, profundidade e confiança, mas cada papel recebe uma influência diferente:

- `outline_detail`: força integral e jitter reduzido;
- `outline_shadow`: 72% da força e jitter moderado;
- `fill_mass`: 32% da força e maior liberdade;
- `texture_accent`: orientação estrutural desativada, usando rotação orgânica.

## Validação

```powershell
python -m pytest -q
```

A suíte cobre:

- determinismo por seed;
- frequência de letras repetidas;
- distribuição exata por zonas, camadas e papéis;
- modulação orgânica estável e limitada;
- profundidade correta de cada subcamada;
- hierarquia de tamanho, opacidade e orientação;
- ordem de pintura do SVG;
- compatibilidade com glyphs antigos sem papel explícito;
- ausência de formas proibidas;
- leitura e validação de máscaras.

## Próximo marco

Depois da validação visual do estilo orgânico, o próximo passo será compor vários objetos semânticos em uma única cena, mantendo um grupo independente para cada objeto e preparando a transição entre dois SVGs.
