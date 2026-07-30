# MP4 Export with FFmpeg

A exportação de vídeo usa os frames PNG produzidos por `animate_scenes.py`. O FFmpeg é uma dependência externa opcional; o pacote Python continua sem bibliotecas de vídeo pesadas.

## Requisitos

O executável `ffmpeg` deve estar no `PATH`, ou seu caminho deve ser informado com `--ffmpeg`.

Verifique no terminal:

```powershell
ffmpeg -version
```

## Exportar uma sequência existente

```powershell
python export_video.py `
  --frames-dir outputs/animations/cat_walk_01/frames/png `
  --output outputs/animations/cat_walk_01/cat_walk_01.mp4 `
  --fps 12
```

Com caminho explícito:

```powershell
python export_video.py `
  --frames-dir outputs/animations/cat_walk_01/frames/png `
  --output outputs/animations/cat_walk_01/cat_walk_01.mp4 `
  --fps 12 `
  --ffmpeg "C:\ffmpeg\bin\ffmpeg.exe"
```

## Qualidade

Controles principais:

- `--crf`: qualidade do H.264, de `0` a `51`; menor significa maior qualidade e arquivo maior. Padrão `18`;
- `--preset`: velocidade de compressão, como `fast`, `medium` ou `slow`. Padrão `medium`.

Exemplo:

```powershell
python export_video.py `
  --frames-dir outputs/frames/png `
  --output outputs/video.mp4 `
  --fps 24 `
  --crf 20 `
  --preset fast
```

## Compatibilidade

O exportador usa:

- codec `libx264`;
- pixel format `yuv420p`;
- `faststart` para reprodução web;
- padding automático para dimensões pares.

Os frames precisam usar nomes contíguos:

```text
frame_0000.png
frame_0001.png
frame_0002.png
...
```

## Demo completo

O comando abaixo executa todo o vertical slice atual:

```powershell
python -m examples.build_cat_walk_video_demo
```

Ele realiza:

1. criação local das máscaras;
2. renderização tipográfica de `CAT`, `MOON` e `GROUND`;
3. composição das duas cenas;
4. interpolação dos objetos;
5. exportação dos frames PNG;
6. codificação do MP4.

Teste menor:

```powershell
python -m examples.build_cat_walk_video_demo `
  --duration 1 `
  --fps 6 `
  --preset fast
```

Saída final:

```text
outputs/demo-cat-walk-video/cat_walk_01.mp4
```

## Próximo passo

Com o primeiro fluxo `objetos → cenas → frames → MP4` concluído, a próxima etapa será criar um Asset Registry e um planner determinístico que converta uma história curta em Scene Graphs.
