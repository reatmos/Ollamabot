import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")
  
import speech_recognition as sr
from ollama import Client
from typing import Generator

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import wave
import pygame
import time
from mutagen.mp3 import MP3
import requests

class OllamaClientChatBot:
    def __init__(
        self,
        model: str = "exaone3.5:2.4b-instruct-q4_K_M",
        system_prompt: str = "당신은 보조 어시스턴트입니다. 최대한 짧게 대답하고, 이모티콘은 쓰지마세요.",
        max_history: int = 5
    ):
        """챗봇 초기화"""
        self.client = Client(host="http://localhost:11434")
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.messages = [{"role": "system", "content": system_prompt}]

    def _trim_history(self):
        """대화 기록을 최대 히스토리 크기로 제한"""
        if len(self.messages) > self.max_history * 2 + 1:
            self.messages = [self.messages[0]] + self.messages[-(self.max_history * 2):]

    def stream_chat(self, user_input: str) -> Generator[str, None, None]:
        """스트리밍 방식으로 챗봇 응답 생성"""
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
    """마이크로부터 음성을 인식하여 텍스트로 변환"""
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        print("\n듣고 있습니다... (음성 입력을 기다리는 중)")
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
    # 음성 인식기와 마이크 초기화
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    # 챗봇 초기화
    bot = OllamaClientChatBot(
        model="exaone3.5:2.4b-instruct-q4_K_M",
        system_prompt="당신은 보조 어시스턴트입니다. 최대한 짧게 대답하고, 이모티콘은 쓰지마세요.",
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
            if user_input.lower() in ["종료", "끝", "대화 종료"]:
                print("대화를 종료합니다.")
                break

            # 챗봇 응답 스트리밍 출력 및 전체 응답 수집
            response_chunks = []
            for chunk in bot.stream_chat(user_input):
                response_chunks.append(chunk)

            # 전체 응답을 하나로 합치기
            full_response = "".join(response_chunks)

            # Use OpenVoice TTS to synthesize speech from Ollama's response
            response = requests.post("http://127.0.0.1:5000/synthesize", json={"text": full_response, "language": "ko"})
            if response.status_code == 200:
                temp_AUDIO_PATH = response.json()["audio_path"]
            else:
                print("TTS synthesis failed.")
                continue
            
            # 오디오 재생 시간 확인 (WAV 파일 처리)
            with wave.open(temp_AUDIO_PATH, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)  # 초 단위

            # 오디오 재생 및 텍스트 동기화
            pygame.mixer.init()
            pygame.mixer.music.load(temp_AUDIO_PATH)

            # 텍스트를 단어와 공백 토큰으로 나누기 (들여쓰기와 공백 유지)
            import re
            tokens = re.findall(r'\S+|\s+', full_response)
            num_tokens = len(tokens)
            time_per_token = duration / num_tokens if num_tokens > 0 else 0

            # 실시간 텍스트 출력
            print("Bot:", end=" ", flush=True)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                current_time = pygame.mixer.music.get_pos() / 1000  # 밀리초 -> 초
                if time_per_token > 0:
                    token_index = int(current_time / time_per_token)
                else:
                    token_index = 0
                if token_index < num_tokens:
                    displayed_text = "".join(tokens[:token_index+1])
                else:
                    displayed_text = full_response
                print("\rBot: " + displayed_text, end="", flush=True)
                time.sleep(0.01)
            print()

        except KeyboardInterrupt:
            print("\n대화를 종료합니다.")
            break