# Prompt Video Studio

O Studio é a interface local para testar o produto sem montar JSONs de job manualmente.

Ele oferece:

- campo de prompt;
- planner determinístico ou Ollama;
- presets de velocidade e qualidade;
- progresso por estágio;
- histórico de gerações;
- preview de frame;
- player MP4 inline;
- download dos artefatos;
- exclusão de jobs concluídos.

## Início rápido

Com o ambiente virtual ativo:

```powershell
python -m commands.studio
```

Esse comando:

1. verifica se o registry padrão já existe;
2. gera os glyph assets aprovados na primeira execução;
3. inicia a FastAPI;
4. abre o navegador em `http://127.0.0.1:8000/studio`.

Para desenvolvimento com reload:

```powershell
python -m commands.studio --reload
```

Também existe um launcher PowerShell:

```powershell
.\scripts\start-studio.ps1 -Reload
```

Na primeira preparação completa:

```powershell
.\scripts\start-studio.ps1 -Install -Reload
```

## Diagnóstico

```powershell
python -m commands.doctor --prepare-assets
```

O diagnóstico verifica:

- versão do Python;
- dependências do projeto;
- catálogo de silhuetas;
- FFmpeg;
- registry padrão do Studio;
- Ollama, como integração opcional.

## Endpoint simplificado

```http
POST /v1/generations
Content-Type: application/json
```

Exemplo:

```json
{
  "prompt": "A cat looks at the moon and then walks away.",
  "provider": "deterministic",
  "preset": "draft",
  "generate_video": true
}
```

Resposta inicial:

```json
{
  "id": "<job-id>",
  "status": "queued",
  "status_url": "/v1/jobs/<job-id>",
  "studio_url": "/studio?job=<job-id>",
  "video_url": "/v1/jobs/<job-id>/video"
}
```

## Presets

### `draft`

- 1 segundo;
- 6 FPS;
- CRF 28;
- preset FFmpeg `ultrafast`.

Adequado para iterar rapidamente em prompts.

### `standard`

- 2 segundos;
- 12 FPS;
- CRF 20;
- preset FFmpeg `veryfast`.

Adequado para revisão comum.

### `quality`

- 4 segundos;
- 24 FPS;
- CRF 18;
- preset FFmpeg `medium`.

Adequado para avaliação visual mais cuidadosa.

Duração, FPS, CRF e preset podem ser substituídos no payload.

## Endpoints do Studio

```text
GET    /studio
GET    /v1/capabilities
POST   /v1/generations
GET    /v1/jobs
GET    /v1/jobs/{job_id}
DELETE /v1/jobs/{job_id}
GET    /v1/jobs/{job_id}/preview
GET    /v1/jobs/{job_id}/video
GET    /v1/jobs/{job_id}/artifacts
GET    /v1/jobs/{job_id}/artifacts/{artifact_path}
```

O endpoint de vídeo usa `video/mp4` e `Content-Disposition: inline`, permitindo reprodução no player HTML.

## Uso com Ollama

```json
{
  "prompt": "O gato observa a lua e caminha para a esquerda.",
  "provider": "ollama",
  "ollama_model": "qwen3:4b",
  "preset": "draft",
  "generate_video": true
}
```

O modelo não cria SVG nem silhuetas. Ele escolhe somente assets já presentes no registry. O fallback determinístico permanece ativado por padrão.

## Registry automático

O Studio prepara e reutiliza:

```text
outputs/_studio/default-assets/asset_registry.json
```

A preparação acontece apenas quando os arquivos obrigatórios não existem. Os jobs ficam separados em:

```text
outputs/api-jobs/<job-id>/
```

## Limitações atuais

- o catálogo narrativo ainda está centrado em `CAT`, `MOON` e `GROUND`;
- cada vídeo usa duas cenas;
- a mudança real entre pose sentada e caminhando ainda não está implementada;
- os jobs usam `BackgroundTasks` no mesmo processo;
- FFmpeg é obrigatório para MP4;
- Ollama é opcional.

O objetivo do Studio nesta fase é reduzir o ciclo de teste para:

```text
prompt → gerar → assistir → ajustar prompt → gerar novamente
```
