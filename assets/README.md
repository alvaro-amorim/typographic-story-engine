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

```text
cat.contemplative → cat_sitting_side_01   (primary)
cat.locomotion    → cat_walking_side_01   (primary)
cat.neutral       → cat_standing_side_01  (secondary)
bird.flight       → bird_flying_side_01   (primary)
```

A sequência `cat_sitting_to_walking_01` continua registrada como `planned`. Isso documenta a intenção narrativa sem afirmar que o morph entre silhuetas já foi implementado.

## Catálogo atual

### Personagens

```text
CAT  → cat_standing_side_01
CAT  → cat_sitting_side_01
CAT  → cat_walking_side_01
BIRD → bird_flying_side_01
```

### Cenário e natureza

```text
MOON   → moon_crescent_01
GROUND → ground_hill_01
STAR   → star_five_point_01
CLOUD  → cloud_soft_01
SUN    → sun_rays_01
TREE   → tree_deciduous_01
```

O registry do Studio contém aliases em português e inglês. Exemplos: `bird/pássaro/ave`, `cloud/nuvem`, `star/estrela`, `sun/sol` e `tree/árvore`.

## Regras

- fundo branco puro e silhueta preta pura;
- `viewBox` obrigatório;
- sem imagens incorporadas, scripts, filtros, gradientes ou recursos externos;
- licença e origem registradas em `metadata.json` e `catalog.json`;
- coordenadas de `anchors` normalizadas entre `0` e `1`;
- um asset aprovado nunca deve mudar silenciosamente: alterações visuais exigem revisão;
- assets `primary` podem ser usados como defaults de produto;
- assets `secondary` permanecem disponíveis, mas não substituem os defaults automaticamente;
- assets externos futuros devem preservar autor, licença e URL de origem reais.

## Construir máscaras

```powershell
python -m commands.build_assets
```

A saída padrão é:

```text
outputs/_asset_cache/<category>/<subject>/<asset-id>/mask.png
```

## Atualizar o cache do Studio

O primeiro início após uma expansão do catálogo reconstrói o pacote automaticamente:

```powershell
python -m commands.studio
```

Para preparar tudo antecipadamente e verificar o ambiente:

```powershell
python -m commands.doctor --prepare-assets
```

Os vetores iniciais deste repositório foram desenhados para o próprio projeto e dedicados a CC0-1.0.
