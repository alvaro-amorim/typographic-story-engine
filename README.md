# Typographic Story Engine

Motor experimental para reconstruir objetos com glyphs semanticamente restritos. Um objeto `MOON`, por exemplo, só pode usar as letras `M`, `O`, `O`, `N`; a repetição do `O` também influencia a frequência de amostragem.

## Estado atual

O MVP recebe uma máscara raster, calcula a distância exata de cada pixel até a borda e gera uma composição tipográfica determinística com três zonas visuais:

- `edge`: contorno com mais glyphs, letras menores e maior opacidade;
- `mid`: transição com densidade e tamanho intermediários;
- `core`: núcleo mais leve, espaçado e com menos sobreposição visual.

O amostrador utiliza uma grade de ocupação espacial para espalhar as letras antes de reutilizar regiões próximas. Um campo de tangentes é calculado a partir do gradiente suavizado do mapa de distância, mas sua influência agora é adaptativa: contorno, profundidade e confiança local determinam quanto cada letra acompanha a curvatura.

Isso mantém o arco organizado nas bordas e reduz faixas radiais ou redemoinhos nas regiões internas instáveis.

Artefatos gerados:

- SVG estrito composto por elementos `<text>`;
- JSON com posição, rotação, tamanho, opacidade, cor, zona, profundidade e orientação de cada glyph;
- relatório de validação semântica, estatísticas por zona e métricas de força efetiva;
- prévia em PNG.

O mapa de distância usa `scipy.ndimage.distance_transform_edt`. A orientação usa `gaussian_filter`, gradiente local, tangentes com confiança normalizada e atenuação por profundidade.

## Instalação no Windows

Crie e ative um ambiente virtual para evitar misturar as dependências do projeto com o Python global:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Confirme que o terminal está usando o Python do ambiente virtual:

```powershell
python -c "import sys; print(sys.executable)"
```

O caminho exibido deve terminar em:

```text
typographic-story-engine\venv\Scripts\python.exe
```

## Testar a orientação adaptativa

Com o `venv` ativo:

```powershell
git fetch origin
git switch agent/adaptive-orientation-field
git pull origin agent/adaptive-orientation-field
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Gere a nova lua:

```powershell
python render_object_from_mask.py `
  --id moon_adaptive `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-adaptive
```

A configuração padrão mantém a divisão:

- 45% dos glyphs para `edge`;
- 35% para `mid`;
- 20% para `core`.

A orientação usa forças máximas mais conservadoras:

- `edge`: `0.90`, mantendo o arco do contorno;
- `mid`: `0.48`, reduzindo faixas internas;
- `core`: `0.12`, permitindo predominância do fallback orgânico.

Além disso:

- suavização padrão do campo: `2.0`;
- confiança mínima base: `0.14`;
- o núcleo exige o dobro da confiança base;
- confiança intermediária é reduzida por expoente `1.60`;
- o efeito da tangente cai progressivamente com a profundidade;
- o jitter é menor no contorno e maior no núcleo.

O relatório registra `orientation_counts`, `mean_tangent_confidence`, `mean_orientation_strength` e `mean_orientation_strength_by_zone`.

## Controles de orientação

- `--orientation-mode tangent|random`: ativa a orientação adaptativa ou usa apenas o fallback;
- `--orientation-smoothing`: suavização antes do gradiente; padrão `2.0`;
- `--orientation-jitter`: jitter base; padrão `7`;
- `--edge-orientation-strength`: força máxima no contorno; padrão `0.90`;
- `--mid-orientation-strength`: força máxima na zona média; padrão `0.48`;
- `--core-orientation-strength`: força máxima no núcleo; padrão `0.12`;
- `--orientation-min-confidence`: confiança mínima base; padrão `0.14`;
- `--orientation-confidence-power`: supressão de confiança média; padrão `1.60`;
- `--rotation-min` e `--rotation-max`: fallback quando a orientação local não é confiável.

Para comparar diretamente com rotações de fallback:

```powershell
python render_object_from_mask.py `
  --id moon_random `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --orientation-mode random `
  --output-dir outputs/moon-random
```

## Controles da distribuição

- `--edge-threshold`: limite de profundidade do contorno; padrão `0.18`;
- `--mid-threshold`: limite entre a zona média e o núcleo; padrão `0.55`;
- `--edge-ratio`, `--mid-ratio`, `--core-ratio`: orçamento relativo de glyphs;
- `--cell-size`: tamanho da célula da grade espacial; padrão `8` pixels;
- `--edge-capacity`, `--mid-capacity`, `--core-capacity`: ocupação inicial máxima por célula;
- `--font-min` e `--font-max`: faixa geral de tamanho;
- `--palette`: uma ou mais cores hexadecimais;
- `--seed`: reproduz exatamente a mesma cena;
- `--skip-png`: gera apenas SVG, JSON e validação.

## Testes

```powershell
python -m pytest -q
```

Os testes verificam:

- determinismo por seed;
- frequência de letras repetidas;
- divisão exata do orçamento por zonas;
- espalhamento por células de ocupação;
- direção das tangentes em bordas horizontais e verticais;
- equivalência de orientação em 180 graus;
- queda da força entre `edge`, `mid` e `core`;
- supressão adicional no núcleo profundo;
- confiança mínima diferente por zona;
- fallback aleatório em regiões instáveis;
- isolamento do estado aleatório global;
- leitura e validação das máscaras.

## Próximo marco

Depois da validação visual da orientação adaptativa, o próximo passo será adicionar camadas tipográficas especializadas: contorno estrutural, preenchimento e textura, cada uma com comportamento visual e de animação próprio.
