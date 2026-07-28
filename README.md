# Typographic Story Engine

Motor experimental para reconstruir objetos com glyphs semanticamente restritos. Um objeto `MOON`, por exemplo, só pode usar as letras `M`, `O`, `O`, `N`; a repetição do `O` também influencia a frequência de amostragem.

## Estado atual

O MVP recebe uma máscara raster, calcula a distância exata de cada pixel até a borda e gera uma composição tipográfica determinística com três zonas visuais:

- `edge`: contorno com mais glyphs, letras menores e maior opacidade;
- `mid`: transição com densidade e tamanho intermediários;
- `core`: núcleo mais leve, espaçado e com menos sobreposição visual.

O amostrador utiliza uma grade de ocupação espacial para espalhar as letras antes de reutilizar regiões próximas. Além disso, um campo de tangentes é calculado a partir do gradiente suavizado do mapa de distância. Assim, as letras acompanham a curvatura local do objeto em vez de receber apenas rotações aleatórias.

Artefatos gerados:

- SVG estrito composto por elementos `<text>`;
- JSON com posição, rotação, tamanho, opacidade, cor, zona, profundidade e orientação de cada glyph;
- relatório de validação semântica, estatísticas por zona e métricas de orientação;
- prévia em PNG.

O mapa de distância usa `scipy.ndimage.distance_transform_edt`. A orientação usa `gaussian_filter`, gradiente local e tangentes com confiança normalizada.

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

## Testar a orientação por curvatura

Com o `venv` ativo:

```powershell
git fetch origin
git switch agent/curvature-aware-orientation
git pull origin agent/curvature-aware-orientation
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Gere a lua em uma nova pasta para comparar com a versão shape-aware:

```powershell
python render_object_from_mask.py `
  --id moon_curvature `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-curvature
```

A configuração padrão mantém a divisão:

- 45% dos glyphs para `edge`;
- 35% para `mid`;
- 20% para `core`.

Também aplica orientação estrutural com forças diferentes:

- `edge`: `0.92`, seguindo fortemente o contorno;
- `mid`: `0.72`, formando fluxo intermediário;
- `core`: `0.38`, preservando mais variação orgânica.

O relatório registra `orientation_counts`, `mean_tangent_confidence` e a configuração completa usada na geração.

## Controles de orientação

- `--orientation-mode tangent|random`: ativa a tangente ou reproduz o comportamento anterior;
- `--orientation-smoothing`: suavização do campo antes do cálculo do gradiente; padrão `1.25`;
- `--orientation-jitter`: variação orgânica em graus; padrão `6`;
- `--edge-orientation-strength`: força estrutural no contorno; padrão `0.92`;
- `--mid-orientation-strength`: força estrutural na zona média; padrão `0.72`;
- `--core-orientation-strength`: força estrutural no núcleo; padrão `0.38`;
- `--orientation-min-confidence`: confiança mínima para usar a tangente; padrão `0.05`;
- `--rotation-min` e `--rotation-max`: fallback aleatório quando a orientação local é instável.

Para comparar diretamente com a versão anterior:

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
- contorno menor e mais opaco que o núcleo;
- direção das tangentes em bordas horizontais e verticais;
- equivalência de orientação em 180 graus;
- fallback aleatório em regiões de baixa confiança;
- isolamento do estado aleatório global;
- leitura e validação das máscaras.

## Próximo marco

Depois da validação visual da orientação, o próximo passo será adicionar camadas tipográficas especializadas: contorno estrutural, preenchimento e textura, cada uma com comportamento visual e de animação próprio.
