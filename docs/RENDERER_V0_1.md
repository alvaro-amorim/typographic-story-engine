# Renderer v0.1 baseline

Esta release congela o primeiro renderer tipográfico considerado satisfatório para avançar ao pipeline de cenas e vídeo.

## Decisão de produto

O projeto não continuará refinando indefinidamente a aparência de um único objeto antes de validar o fluxo completo. A partir desta versão, mudanças visuais no SVG serão tratadas como ajustes incrementais e compatíveis, não como bloqueadores do Scene Composer.

## Renderer recomendado

O baseline oficial é o renderer balanceado disponível em `render_balanced_from_mask.py`.

Ele combina:

- SVG estrito cuja arte visível é composta somente por elementos `<text>`;
- caracteres limitados à palavra semântica de cada objeto;
- repetição de letras preservada na frequência de amostragem;
- geração determinística por seed;
- análise de profundidade e curvatura da máscara;
- distribuição espacial com controle de concentração;
- contorno em detalhe e sombra interna;
- preenchimento uniforme com microvariações controladas;
- textura leve e distribuída;
- JSON completo dos glyphs e relatório de validação.

## Modos preservados

Os renderers anteriores permanecem no código para comparação e regressão:

- `legacy`: distribuição por zonas;
- `layered`: outline, fill e texture independentes;
- `organic`: direção artística com modulação orgânica mais forte;
- `balanced`: baseline aprovado desta release.

## Comando de referência

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

## Contrato mínimo do renderer

Uma alteração futura não pode quebrar estes invariantes:

1. A mesma entrada e a mesma seed produzem o mesmo estado de glyphs.
2. Cada objeto usa somente os caracteres permitidos por sua própria palavra.
3. Nenhuma forma geométrica visível substitui os glyphs.
4. Cada glyph possui ID estável, objeto, posição, tamanho, rotação, opacidade, cor, camada e papel visual.
5. O SVG, o JSON, o PNG e o relatório de validação continuam disponíveis.
6. O renderer pode ser chamado como biblioteca pelo futuro compositor de cenas.

## Próximo marco

O próximo desenvolvimento é o vertical slice end-to-end:

1. Scene Graph e Scene Composer multiobjeto;
2. composição de `CAT + MOON + GROUND`;
3. duas cenas com IDs persistentes;
4. animação inicial por transformações de grupos SVG;
5. exportação de frames e MP4;
6. Asset Registry e Story Planner;
7. API mínima.

O matching individual de milhares de glyphs entre cenas será implementado somente depois que a animação por objeto provar o fluxo completo.