# Configure Ollama for GPU acceleration on Windows with RTX 5070
Write-Host "Configuring Ollama for GPU acceleration..." -ForegroundColor Green

# Set GPU layers (adjust based on your model size and VRAM)
# For 7B models: 20-30 layers
# For 12B models: 25-35 layers  
# For 30B models: 30-40 layers
$env:OLLAMA_GPU_LAYERS = 35

# Optional: Set other performance options
# $env:OLLAMA_NUM_PARALLEL = 2
# $env:OLLAMA_MAX_LOADED_MODELS = 3

Write-Host "`nCurrent GPU status:" -ForegroundColor Yellow
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv

Write-Host "`nTo apply these settings:" -ForegroundColor Green
Write-Host "1. These environment variables are set for this session" -ForegroundColor White
Write-Host "2. Restart Ollama: Stop and start the Ollama service" -ForegroundColor White
Write-Host "3. Verify with: nvidia-smi" -ForegroundColor White

Write-Host "`nExample for persistent setup:" -ForegroundColor Green
Write-Host '[System.Environment]::SetEnvironmentVariable("OLLAMA_GPU_LAYERS="35","User"' -ForegroundColor White
