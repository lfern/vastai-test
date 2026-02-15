./vastai-scripts/set-api-key.sh c69fff3a81a71e6f8d95115313b0fa37179368fe5664900c3738948354088e3d


./vastai-scripts/search-offers.sh "dph<0.15 reliability>0.99 gpu_name=RTX_3090 num_gpus=1 gpu_ram>24 cpu_ram>32" -o dph

./vastai-scripts/create-instance.sh <OFFER_ID> --image vastai/ollama:0.15.4 --env '-p 21434:21434 -e OLLAMA_MODEL=glm-4.7-flash -e PORTAL_CONFIG="localhost:1111:11111:/:Instance Portal|localhost:21434:11434:/:Ollama API|localhost:8080:18080:/:Jupyter|localhost:8080:8080:/terminals/1:Jupyter Terminal" -e OPEN_BUTTON_PORT=1111 -e OPEN_BUTTON_TOKEN=1 -e JUPYTER_DIR=/ -e DATA_DIRECTORY=/workspace/' --onstart-cmd 'entrypoint.sh' --disk 32

