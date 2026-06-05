# Fooocus local image generator

Fooocus is an optional local image generator for ERA_MEDIA visual work. It runs separately from the editor pipeline and gives the operator a local browser UI for generating MAX post visuals.

Official repo: https://github.com/lllyasviel/Fooocus

## What this adds

- Docker build config under `docker/fooocus/`.
- Optional compose override: `docker-compose.fooocus.yml`.
- Persistent model volume: `fooocus_models`.
- Generated outputs mounted to `./generated_media/fooocus` so ERA_MEDIA can reuse files later.
- Default UI port: `7865`.

## Requirements

Recommended:

- Windows/macOS/Linux with Docker.
- NVIDIA GPU with enough VRAM.
- NVIDIA Container Toolkit if using Linux Docker Engine.
- 20GB+ free disk for SDXL/Fooocus models.

Fooocus can be heavy. Do not run it on small VPS nodes; run it on a local workstation.

## First run

From repo root:

```bash
cp .env.example .env
make fooocus-up
```

Or directly:

```bash
docker compose -f docker-compose.yml -f docker-compose.fooocus.yml --profile fooocus up --build fooocus
```

Open:

```text
http://127.0.0.1:7865
```

The first launch downloads models automatically. This can take time.

## Stop

```bash
make fooocus-down
```

Or:

```bash
docker compose -f docker-compose.yml -f docker-compose.fooocus.yml --profile fooocus down
```

## Useful env vars

Set in `.env`:

```env
FOOOCUS_PORT=7865
FOOOCUS_REF=main
FOOOCUS_ARGS=--preset realistic --always-download-new-model
NVIDIA_VISIBLE_DEVICES=all
```

Preset examples:

```env
FOOOCUS_ARGS=--preset realistic --always-download-new-model
FOOOCUS_ARGS=--preset anime --always-download-new-model
FOOOCUS_ARGS=--always-download-new-model
```

## How to use with ERA_MEDIA

1. Generate an image in Fooocus UI.
2. Take the generated file from:

```text
./generated_media/fooocus
```

3. Use it as a reviewed visual for a MAX post.

Recommended workflow:

```text
ERA_MEDIA draft -> Fooocus visual -> operator review -> attach media -> manual MAX publish
```

Do not use generated images as documentary proof. For news, label/handle them as illustrative visuals only.

## Troubleshooting

### Docker says GPU is unavailable

Check NVIDIA runtime:

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

If it fails, install/update NVIDIA Container Toolkit or use Fooocus outside Docker.

### First run is slow

Normal. Fooocus downloads SDXL checkpoints and inpaint models on first use.

### Port busy

Set another port:

```bash
FOOOCUS_PORT=7866 make fooocus-up
```

### Need manual model files

Put models in Docker volume by running the container once, or bind your own model directory by editing `docker-compose.fooocus.yml`:

```yaml
volumes:
  - /path/to/local/models:/opt/fooocus/models
  - ./generated_media/fooocus:/opt/fooocus/outputs
```
