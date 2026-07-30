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

## Regras

- fundo branco puro e silhueta preta pura;
- `viewBox` obrigatório;
- sem imagens incorporadas, scripts, filtros, gradientes ou recursos externos;
- licença e origem registradas em `metadata.json` e `catalog.json`;
- coordenadas de `anchors` normalizadas entre `0` e `1`;
- um asset aprovado nunca deve mudar silenciosamente: alterações visuais exigem revisão.

## Construir máscaras

```powershell
python -m commands.build_assets
```

A saída padrão é:

```text
outputs/_asset_cache/<category>/<subject>/<asset-id>/mask.png
```

Os vetores iniciais deste repositório foram desenhados para o próprio projeto e dedicados a CC0-1.0. Assets externos adicionados no futuro devem preservar a licença e a URL de origem reais.
