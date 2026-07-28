# Controlled Organic Balance

Este modo combina o melhor dos renderers anteriores:

- contorno variável do modo `organic`;
- preenchimento limpo e espacialmente distribuído do modo `layered`;
- textura visível, porém sem clusters de alta densidade.

## Decisões visuais

O contorno continua dividido em:

- `outline_detail`: pequeno, opaco e fortemente orientado;
- `outline_shadow`: maior, mais suave e deslocado para dentro.

O interior muda de estratégia:

- `fill_mass` não seleciona mais regiões de alta modulação orgânica;
- a amostragem usa round-robin espacial com capacidade inicial de um glyph por célula;
- a modulação do fill é limitada a uma microvariação em torno de 0,5;
- a cor mais escura tem probabilidade padrão de apenas 8% no fill;
- tamanho e opacidade têm intervalos menores para evitar manchas.

A textura também usa distribuição espacial uniforme, menor orçamento e opacidade controlada.

## Gerar a lua balanceada

Com o `venv` ativo:

```powershell
python render_balanced_from_mask.py `
  --id moon_balanced `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-balanced
```

A divisão padrão é:

```text
outline=2720, fill=4480, texture=800
outline_shadow=707, outline_detail=2013
```

## Comparação recomendada

Compare com o modo `layered`:

```powershell
python render_object_from_mask.py `
  --id moon_layered_compare `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --layer-mode layered `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-layered-compare
```

E com o modo `organic`:

```powershell
python render_object_from_mask.py `
  --id moon_organic_compare `
  --word MOON `
  --mask moon_mask.png `
  --count 8000 `
  --seed 817392 `
  --layer-mode organic `
  --palette "#172033" "#344966" "#596773" "#8A795D" `
  --output-dir outputs/moon-organic-compare
```

## Métricas novas

O relatório `*_validation.json` inclui `balanced_role_metrics` com:

- contagem por papel;
- tamanho médio;
- opacidade média;
- força média de orientação;
- profundidade média;
- maior concentração de glyphs em uma célula métrica de 32 pixels.

Essa última métrica ajudará a detectar regressões de clustering sem depender apenas da inspeção visual.
