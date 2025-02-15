import speech_recognition as sr
from ollama import Client
from typing import Generator
from translate import Translator  # new import for translation
from gtts import gTTS  # new import for TTS
import os                 # new import for playing audio
import tempfile          # new import for temporary file handling

class OllamaClientChatBot:
    def __init__(
        self,
        model: str = "exaone3.5:2.4b-instruct-q4_K_M",
        system_prompt: str = "You are a helpful assistant.",
        max_history: int = 5
    ):
        self.client = Client(host="http://localhost:11434")
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.messages = [
            {"role": "system", "content": system_prompt}
        ]

    def _trim_history(self):
        """최근 대화 기록만 유지"""
        if len(self.messages) > self.max_history * 2 + 1:
            self.messages = [self.messages[0]] + self.messages[-(self.max_history * 2):]

    def stream_chat(self, user_input: str) -> Generator[str, None, None]:
        """스트리밍 채팅 응답 생성"""
        self.messages.append({"role": "user", "content": user_input})
        
        full_response = []
        stream = self.client.chat(
            model=self.model,
            messages=self.messages,
            stream=True
        )
        
        try:
            for chunk in stream:
                if chunk['message']['content']:
                    chunk_content = chunk['message']['content']
                    full_response.append(chunk_content)
                    yield chunk_content
                    
            self.messages.append({"role": "assistant", "content": "".join(full_response)})
            self._trim_history()
            
        except Exception as e:
            yield f"\n[ERROR: {str(e)}]"


def recognize_speech_from_mic(recognizer, microphone):
    """마이크로부터 음성을 인식하고 텍스트로 변환"""
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        print("듣고 있습니다... (음성 입력을 기다리는 중)")
        audio = recognizer.listen(source)
        try:
            return recognizer.recognize_google(audio, language="ko-KR")
        except sr.UnknownValueError:
            print("음성을 이해할 수 없습니다.")
            return None
        except sr.RequestError as e:
            print(f"Google Speech Recognition 서비스에 접근할 수 없습니다: {e}")
            return None


if __name__ == "__main__":
    # 음성 인식기 및 마이크 초기화
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    # 번역기 초기화 (일본어 번역)
    translator = Translator(to_lang="ja", from_lang="ko")

    # 챗봇 초기화
    bot = OllamaClientChatBot(
        model="exaone3.5:2.4b-instruct-q4_K_M",
        system_prompt="간결한 한국어로 답변해 주세요. 반말을 사용하지 말고 존댓말을 사용하세요.",
        max_history=3
    )

    print("챗봇을 시작합니다 (종료: '종료'라고 말하세요)")
    while True:
        try:
            # 음성 입력 받기
            user_input = recognize_speech_from_mic(recognizer, microphone)
            if user_input is None:
                continue

            print(f"\nYou: {user_input}")
            if user_input.lower() in ["종료", "끝"]:
                print("대화를 종료합니다.")
                break

            # 챗봇 응답 스트리밍 출력 및 전체 응답 수집
            print("Bot:", end=" ", flush=True)
            response_chunks = []
            for chunk in bot.stream_chat(user_input):
                print(chunk, end="", flush=True)
                response_chunks.append(chunk)
            print()

            full_response = "".join(response_chunks)
            # 텍스트를 일본어로 번역 후 출력
            translated_text = translator.translate(full_response)
            print("翻訳 (Japanese):", translated_text)
            
            # TTS로 일본어 번역된 텍스트 출력
            tts = gTTS(translated_text, lang='ja')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_audio_path = fp.name
            tts.save(temp_audio_path)
            # Play audio directly using playsound
            from playsound import playsound
            playsound(temp_audio_path)

        except KeyboardInterrupt:
            print("\n대화를 종료합니다.")
            break
