import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")

from flask import Flask, request, jsonify
from tts_openvoice import synthesize_speech  # 모델 로딩 및 음성 합성 함수 재사용
import threading

app = Flask(__name__)

@app.route("/synthesize", methods=["POST"])
def synthesize():
    data = request.get_json()
    text = data.get("text", "")
    language = data.get("language", "ko")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    # synthesize_speech 함수 내부에서 TTS 모델이 캐싱되어 있다면, 이미 로드되어 있음.
    audio_path = synthesize_speech(text, language)
    return jsonify({"audio_path": audio_path})

def run_app():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    # 별도 스레드로 플라스크 서버 실행 가능
    server_thread = threading.Thread(target=run_app)
    server_thread.start()