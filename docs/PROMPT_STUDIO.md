# Prompt Video Studio

O Studio é a interface local para testar o produto sem montar JSONs de job manualmente.

Ele oferece:

- campo de prompt;
- planner determinístico ou Ollama;
- descoberta automática dos modelos Ollama instalados;
- teste real de inferência e medição de latência;
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
- versão do Ollama;
- nomes dos modelos Ollama instalados;
- latência da descoberta local.

URL e timeout também podem ser informados:

```powershell
python -m commands.doctor `
  --ollama-url http://localhost:11434 `
  --ollama-timeout 5
```

## Ollama no frontend

1. Inicie o Ollama local.
2. Abra o Studio.
3. Selecione `Ollama local` no campo `Planner`.
4. O Studio consulta `/api/version` e `/api/tags` através da própria FastAPI.
5. Escolha um modelo na lista de modelos instalados.
6. Clique em `Testar modelo` para executar uma inferência mínima.
7. Gere o vídeo.

O painel informa:

- versão do servidor Ollama;
- quantidade de modelos encontrados;
- tamanho e quantização quando disponíveis;
- latência da descoberta;
- tempo da inferência de teste;
- modelo solicitado;
- planner realmente utilizado;
- ocorrência de fallback determinístico.

A URL, o modelo, o timeout e a opção de fallback são preservados no navegador.

## Endpoint simplificado

```http
POST /v1/generations
Content-Type: application/json
```

Exemplo determinístico:

```json
{
  "prompt": "A cat looks at the moon and then walks away.",
  "provider": "deterministic",
  "preset": "draft",
  "generate_video": true
}
```

Exemplo com Ollama:

```json
{
  "prompt": "O gato observa a lua e caminha para a esquerda.",
  "provider": "ollama",
  "ollama_model": "qwen3:4b",
  "ollama_url": "http://localhost:11434",
  "ollama_timeout": 60,
  "fallback_to_deterministic": true,
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

## Endpoints de Ollama

```text
GET  /v1/ollama/status
POST /v1/ollama/test
```

Descoberta:

```http
GET /v1/ollama/status?base_url=http://localhost:11434&timeout_seconds=2
```

Teste de modelo:

```json
{
  "base_url": "http://localhost:11434",
  "model": "qwen3:4b",
  "timeout_seconds": 60
}
```

A descoberta é leve. O teste carrega o modelo e executa uma geração curta, portanto a primeira execução pode levar mais tempo.

## Presets

### `draft`

- 1 segundo;
- 6 FPS;
- CRF 28;
- preset FFmpeg `ultrafast`.

### `standard`

- 2 segundos;
- 12 FPS;
- CRF 20;
- preset FFmpeg `veryfast`.

### `quality`

- 4 segundos;
- 24 FPS;
- CRF 18;
- preset FFmpeg `medium`.

Duração, FPS, CRF e preset podem ser substituídos no payload.

## Endpoints do Studio

```text
GET    /studio
GET    /v1/capabilities
GET    /v1/ollama/status
POST   /v1/ollama/test
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

## Fallback

O modelo não cria SVG nem silhuetas nesta versão. Ele escolhe somente assets presentes no registry.

Quando `fallback_to_deterministic` está ativado e o Ollama falha, o job continua com o planner determinístico. O Studio mostra separadamente:

```text
Planner solicitado: ollama
Planner efetivo: deterministic
Fallback: Sim — determinístico usado
```

Para avaliar o Ollama sem esconder falhas, desative a opção de fallback.

## Registry automático

O Studio prepara e reutiliza:

```text
outputs/_studio/default-assets/asset_registry.json
```

Os jobs ficam separados em:

```text
outputs/api-jobs/<job-id>/
```

## Limitações atuais

- o Ollama ainda seleciona apenas assets existentes;
- novos conceitos ainda não geram silhuetas automaticamente;
- cada vídeo usa duas cenas;
- a mudança real entre pose sentada e caminhando ainda não está implementada;
- os jobs usam `BackgroundTasks` no mesmo processo;
- FFmpeg é obrigatório para MP4;
- Ollama é opcional.

O próximo marco do planner será substituir a decisão mínima por um storyboard estruturado com várias cenas, objetos, ações, relações e durações.
