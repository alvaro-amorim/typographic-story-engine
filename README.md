# Typographic Story Engine

Motor experimental para reconstruir objetos com glyphs semanticamente restritos. Um objeto `MOON`, por exemplo, só pode usar as letras `M`, `O`, `O`, `N`; a repetição do `O` também influencia a frequência de amostragem.

## Estado atual

O MVP recebe uma máscara raster, calcula a distância de cada pixel até a borda, distribui glyphs de forma determinística e gera:

- SVG estrito composto por elementos `<text>`;
- JSON com os glyphs;
- relatório de validação semântica;
- prévia em PNG.

## Instalação no Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Gerar uma cena

```powershell
python render_object_from_mask.py `
  --id moon_01 `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --output-dir outputs/moon
```

Parâmetros úteis:

- `--font-min` e `--font-max`: controlam o tamanho dos glyphs;
- `--rotation-min` e `--rotation-max`: controlam a rotação;
- `--palette`: recebe uma ou mais cores hexadecimais;
- `--seed`: reproduz exatamente a mesma cena;
- `--skip-png`: gera apenas SVG, JSON e validação.

Exemplo de paleta:

```powershell
--palette "#2C303A" "#4F5D75" "#BFC0C0" "#EAE2B7"
```

## Testes

```powershell
pytest -q
```

Os testes verificam determinismo, preservação da frequência de letras repetidas, isolamento do estado aleatório global, limites visuais e validação dos modelos.

## Próximo marco

A próxima etapa é evoluir de amostragem aleatória uniforme para amostragem orientada por borda, contraste e densidade, mantendo IDs estáveis para animação entre cenas.
