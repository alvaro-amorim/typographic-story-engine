# Multi-object Scene Composer

O Scene Composer combina objetos tipográficos já renderizados sem recalcular seus glyphs. Cada objeto mantém coordenadas locais e recebe transformação no grupo SVG.

## Por que separar renderização e composição

O renderer de objeto resolve máscara, densidade, orientação, camadas e semântica. O compositor resolve apenas:

- posição;
- escala independente nos eixos;
- rotação;
- opacidade;
- visibilidade;
- ordem por `z_index`;
- validação semântica por objeto.

Mover um objeto não altera seu JSON de glyphs. Essa separação será usada na animação entre cenas.

## Formato de cena

```json
{
  "id": "cat_moon_ground_01",
  "width": 1280,
  "height": 720,
  "background": "#F5F1E8",
  "objects": [
    {
      "id": "moon_01",
      "word": "MOON",
      "glyphs_path": "../objects/moon/moon_01_scene.json",
      "z_index": 1,
      "transform": {
        "x": 900,
        "y": 45,
        "scale_x": 0.62,
        "scale_y": 0.62,
        "rotation": -7,
        "opacity": 1
      }
    }
  ]
}
```

Caminhos relativos são resolvidos a partir do diretório do JSON da cena.

## Uso direto

Primeiro renderize os objetos:

```powershell
python render_object_from_mask.py `
  --id moon_01 `
  --word MOON `
  --mask moon_mask.png `
  --count 3000 `
  --output-dir outputs/objects/moon
```

Depois componha a cena:

```powershell
python render_scene.py `
  --scene examples/scenes/cat_moon_ground.json `
  --output-dir outputs/scenes
```

## Demo completo

O demo cria máscaras locais simples, renderiza os três objetos e monta a cena:

```powershell
python examples/build_cat_moon_ground_demo.py
```

Para executar mais rápido sem PNG:

```powershell
python examples/build_cat_moon_ground_demo.py --skip-png
```

Saídas principais:

```text
outputs/demo-cat-moon-ground/
├── masks/
├── objects/
├── cat_moon_ground_scene.json
└── scene/
    └── cat_moon_ground_01/
        ├── cat_moon_ground_01_scene.svg
        ├── cat_moon_ground_01_scene.json
        ├── cat_moon_ground_01_validation.json
        └── cat_moon_ground_01_preview.png
```

## Estrutura do SVG

```text
scene_<scene_id>
├── object_moon_01
│   ├── moon_01_layer_texture
│   ├── moon_01_layer_fill
│   └── moon_01_layer_outline
├── object_ground_01
└── object_cat_01
```

A arte visível continua sendo formada somente por elementos `<text>`. Os grupos `<g>` organizam objetos, camadas e papéis visuais.

## Validação

O relatório verifica:

- caracteres permitidos separadamente para cada objeto;
- ausência de tags geométricas visíveis proibidas;
- IDs globais de glyphs sem duplicação;
- presença do grupo SVG de cada objeto visível;
- ordem de pintura por `z_index`.

## Próximo passo

A próxima etapa reutilizará dois Scene Graphs com os mesmos IDs de objeto e interpolará `x`, `y`, `scale_x`, `scale_y`, `rotation` e `opacity` para gerar frames de animação.
