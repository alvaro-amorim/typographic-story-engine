# Typographic Story Engine

Motor experimental para reconstruir objetos com glyphs semanticamente restritos. Um objeto `MOON`, por exemplo, só pode usar as letras `M`, `O`, `O`, `N`; a repetição do `O` também influencia a frequência de amostragem.

## Estado atual

O MVP recebe uma máscara raster, calcula a distância exata de cada pixel até a borda e gera uma composição tipográfica determinística com três zonas visuais:

- `edge`: contorno com mais glyphs, letras menores e maior opacidade;
- `mid`: transição com densidade e tamanho intermediários;
- `core`: núcleo mais leve, espaçado e com menos sobreposição visual.

O amostrador utiliza uma grade de ocupação espacial para espalhar as letras antes de reutilizar regiões próximas. O objetivo é preservar o contorno sem transformar o centro em uma mancha escura.

Artefatos gerados:

- SVG estrito composto por elementos `<text>`;
- JSON com posição, rotação, tamanho, opacidade, cor, zona e profundidade de cada glyph;
- relatório de validação semântica e estatísticas por zona;
- prévia em PNG.

O mapa de distância usa `scipy.ndimage.distance_transform_edt`, preservando medidas euclidianas precisas para controlar as zonas e os estilos visuais.

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

O nome `(venv)` no início da linha do PowerShell também indica que o ambiente está ativo.

## Testar a distribuição shape-aware

Com o `venv` ativo:

```powershell
git fetch origin
git switch agent/shape-aware-glyph-distribution
git pull origin agent/shape-aware-glyph-distribution
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Gere a mesma lua em uma nova pasta para comparar com o resultado anterior:

```powershell
python render_object_from_mask.py `
  --id moon_shape_aware `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-shape-aware
```

A configuração padrão reserva:

- 45% dos glyphs para `edge`;
- 35% para `mid`;
- 20% para `core`.

Para 8.000 glyphs, o relatório deve registrar aproximadamente:

```json
{
  "zone_counts": {
    "edge": 3600,
    "mid": 2800,
    "core": 1600
  }
}
```

Os valores podem ser redistribuídos automaticamente quando uma máscara não possui pixels em alguma zona.

## Controles da distribuição

- `--edge-threshold`: limite de profundidade do contorno; padrão `0.18`;
- `--mid-threshold`: limite entre a zona média e o núcleo; padrão `0.55`;
- `--edge-ratio`, `--mid-ratio`, `--core-ratio`: orçamento relativo de glyphs;
- `--cell-size`: tamanho da célula da grade espacial; padrão `8` pixels;
- `--edge-capacity`, `--mid-capacity`, `--core-capacity`: ocupação inicial máxima por célula;
- `--font-min` e `--font-max`: faixa geral de tamanho;
- `--rotation-min` e `--rotation-max`: faixa de rotação;
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
- redistribuição quando uma zona não existe;
- isolamento do estado aleatório global;
- leitura e validação das máscaras.

## Próximo marco

Depois de validar visualmente o zoneamento, o próximo passo será orientar a rotação dos glyphs pela tangente local da forma, fazendo as letras acompanharem curvas como o arco da lua.
