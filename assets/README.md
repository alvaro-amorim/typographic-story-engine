# Curated silhouette assets

Esta pasta contém as referências visuais aprovadas usadas pelo renderer. O pipeline nunca baixa imagens durante a geração e o planner não cria silhuetas: ele apenas seleciona IDs existentes no catálogo.

## Estrutura

```text
assets/
├── catalog.json
└── silhouettes/
    ├── characters/<subject>/<asset-id>/
    │   ├── source.svg
    │   └── metadata.json
    └── environments/<subject>/<asset-id>/
        ├── source.svg
        └── metadata.json
```

`source.svg` é a referência editável em preto e branco. As máscaras PNG são derivadas e geradas em `outputs/_asset_cache/`; elas não são versionadas.

## Baseline visual aprovado

O catálogo v0.2.2 registra funções explícitas para evitar trocas silenciosas de pose:

```text
cat.contemplative → cat_sitting_side_01   (primary)
cat.locomotion    → cat_walking_side_01   (primary)
cat.neutral       → cat_standing_side_01  (secondary)
```

A sequência `cat_sitting_to_walking_01` também está registrada como `planned`. Isso documenta a intenção narrativa sem afirmar que o morph entre silhuetas já foi implementado. Enquanto essa transição não existir, cada animação continua usando uma única fonte de glyphs persistente.

## Regras

- fundo branco puro e silhueta preta pura;
- `viewBox` obrigatório;
- sem imagens incorporadas, scripts, filtros, gradientes ou recursos externos;
- licença e origem registradas em `metadata.json` e `catalog.json`;
- coordenadas de `anchors` normalizadas entre `0` e `1`;
- um asset aprovado nunca deve mudar silenciosamente: alterações visuais exigem revisão;
- assets `primary` podem ser usados como defaults de produto;
- assets `secondary` permanecem disponíveis, mas não substituem os defaults automaticamente.

## Construir máscaras

```powershell
python -m commands.build_assets
```

A saída padrão é:

```text
outputs/_asset_cache/<category>/<subject>/<asset-id>/mask.png
```

Os vetores iniciais deste repositório foram desenhados para o próprio projeto e dedicados a CC0-1.0. Assets externos adicionados no futuro devem preservar a licença e a URL de origem reais.
