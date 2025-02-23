# Ollamabot
Chatbot use by Ollama

## Requirements
- [Ollama](https://ollama.com/download)
- [checkpoints v2](https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip)

## Library
- pip install numpy flask SpeechRecognition torch nltk wave pygame
- pip install git+https://github.com/myshell-ai/MeloTTS.git

## How to Run
1. Download checkpoints v2 and Extract in library/OpenVoice
2. Install Ollama
3. Pull AI Model on Ollama
4. Run Ollama
5. Edit line 20 `model: str = "exaone3.5:2.4b-instruct-q4_K_M"` and line 82 `model="exaone3.5:2.4b-instruct-q4_K_M"` to your model
6. Run `python tts_daemon.py` on other terminal
7. Run main.py and Talk Korean

## Note
1. https://pagichacha.tistory.com/293

## And..
Run failed in Raspberry Pi :(
