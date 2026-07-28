# Typographic Story Engine

Motor experimental para reconstruir objetos com glyphs semanticamente restritos. Um objeto `MOON`, por exemplo, só pode usar as letras `M`, `O`, `O`, `N`; a repetição do `O` também influencia a frequência de amostragem.

## Estado atual

O MVP recebe uma máscara raster, calcula a distância de cada pixel até a borda, distribui glyphs de forma determinística e gera:

- SVG estrito composto por elementos `<text>`;
- JSON com os glyphs;
- relatório de validação semântica;
- prévia em PNG.

O cálculo de distância é implementado no próprio projeto com NumPy. O núcleo não depende de SciPy, Cairo ou outras bibliotecas científicas nativas difíceis de instalar no Windows.

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

Também é possível executar explicitamente pelo ambiente virtual sem ativá-lo:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

## Atualizar a branch de desenvolvimento

```powershell
git fetch origin
git switch agent/deterministic-core
git pull origin agent/deterministic-core
python -m pip install -r requirements-dev.txt
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
python -m pytest -q
```

Os testes verificam determinismo, preservação da frequência de letras repetidas, isolamento do estado aleatório global, limites visuais, análise de máscaras sem SciPy e validação dos modelos.

## Solução para instalações anteriores

Versões anteriores do projeto usavam SciPy. Depois de atualizar a branch, ele não é mais necessário. Você pode mantê-lo instalado porque o projeto não fará o import, ou removê-lo do ambiente virtual:

```powershell
python -m pip uninstall scipy -y
python -m pip install -r requirements-dev.txt
```

## Próximo marco

A próxima etapa é evoluir de amostragem aleatória uniforme para amostragem orientada por borda, contraste e densidade, mantendo IDs estáveis para animação entre cenas.
