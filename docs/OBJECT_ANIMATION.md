# Object-level Scene Animation

A primeira versão de animação move grupos SVG completos. Os glyphs não são regenerados entre frames.

## Contrato entre as cenas

As cenas inicial e final precisam ter:

- mesmo tamanho de canvas;
- mesmo fundo;
- mesmos IDs de objeto;
- mesma palavra para cada ID;
- mesmo arquivo de glyphs para cada ID;
- mesmo `z_index`.

Podem mudar:

- `x` e `y`;
- `scale_x` e `scale_y`;
- `rotation`;
- `opacity`;
- `visible`.

Mudanças de visibilidade são convertidas em fade por opacidade, mantendo o grupo presente durante a transição.

## Formato da animação

```json
{
  "id": "cat_walk_01",
  "from_scene": "cat_walk_start.json",
  "to_scene": "cat_walk_end.json",
  "duration_seconds": 2.0,
  "fps": 12,
  "easing": "ease_in_out"
}
```

Easings disponíveis:

- `linear`;
- `ease_in`;
- `ease_out`;
- `ease_in_out`.

## Gerar frames

```powershell
python animate_scenes.py `
  --animation examples/animations/cat_walk.json `
  --output-dir outputs/animations
```

Para gerar somente SVG e acelerar testes:

```powershell
python animate_scenes.py `
  --animation examples/animations/cat_walk.json `
  --output-dir outputs/animations `
  --skip-png
```

## Demo completo

O demo cria máscaras, renderiza `CAT`, `MOON` e `GROUND`, monta duas cenas e gera a transição:

```powershell
python -m examples.build_cat_walk_animation_demo
```

Teste rápido:

```powershell
python -m examples.build_cat_walk_animation_demo `
  --duration 1 `
  --fps 4 `
  --skip-png
```

## Saídas

```text
outputs/demo-cat-walk/
├── cat_walk_start.json
├── cat_walk_end.json
├── cat_walk_animation.json
└── animation/
    └── cat_walk_01/
        ├── cat_walk_01_manifest.json
        ├── cat_walk_01_validation.json
        └── frames/
            ├── svg/
            └── png/
```

## Persistência

O manifest registra, para cada frame:

- índice;
- timestamp;
- progresso linear;
- progresso após easing;
- transformação de cada objeto.

Os estados locais dos glyphs permanecem idênticos em todos os frames. Apenas o grupo do objeto recebe transformação.

## Próximo passo

A próxima etapa adicionará exportação MP4 com FFmpeg usando os frames PNG já produzidos.
