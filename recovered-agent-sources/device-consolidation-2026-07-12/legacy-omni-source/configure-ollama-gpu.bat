@echo off
REM Configure Ollama for GPU acceleration on Windows with RTX 5070
echo Configuring Ollama for GPU acceleration...

REM Set GPU layers (adjust based on your model size and VRAM)
REM For 7B models: 20-30 layers
REM For 12B models: 25-35 layers  
REM For 30B models: 30-40 layers
set OLLAMA_GPU_LAYERS=35

REM Optional: Set other performance options
rem set OLLAMA_NUM_PARALLEL=2
rem set OLLAMA_MAX_LOADED_MODELS=3

echo.
echo Current GPU configuration:
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv

echo.
echo To apply these settings:
echo 1. Set the environment variables in your shell
echo 2. Restart Ollama service
echo 3. Verify with: nvidia-smi

echo.
echo Example usage:
echo set OLLAMA_GPU_LAYERS=35
echo ollama serve
echo.
pause
