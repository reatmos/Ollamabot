import warnings
# FutureWarning 관련 torch.nn.utils.weight_norm 모듈의 경고 메시지를 숨깁니다.
warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")

import speech_recognition as sr
from ollama import Client
from typing import Generator, Union, List

import os
# Pygame의 지원 메시지가 출력되지 않도록 설정합니다.
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import wave
import pygame
import time
import requests
from rich import print as rprint
from rich.live import Live
from rich.console import Console

import re
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text

def retrieve_context(sources: Union[str, List[str]]) -> str:
    """
    주어진 sources (파일 경로 또는 URL)의 내용을 읽어와 하나의 문자열로 합칩니다.
    - sources가 단일 문자열이라면 리스트로 감싸서 처리합니다.
    - 폴더인 경우, 폴더 내의 텍스트(.txt)와 PDF(.pdf) 파일들을 읽어옵니다.
    """
    if isinstance(sources, str):
        sources = [sources]
    
    contexts = []
    for source in sources:
        # 해당 source가 디렉터리이면 하위의 텍스트/PDF 파일들을 대상에 포함시킴
        if os.path.isdir(source):
            folder_files = [
                os.path.join(source, fname)
                for fname in os.listdir(source)
                if os.path.isfile(os.path.join(source, fname)) and fname.lower().endswith(('.txt', '.pdf'))
            ]
            for file_path in folder_files:
                contexts.append(process_file_or_url(file_path))
        else:
            # 파일이나 URL이면 바로 처리
            contexts.append(process_file_or_url(source))
    # 여러 개의 context를 두 줄 간격으로 구분하여 합침
    return "\n\n".join(contexts)

def process_file_or_url(source: str) -> str:
    """
    주어진 파일 경로나 URL의 내용을 읽어옵니다.
    - 텍스트 파일의 경우 단순히 파일 내용을 읽습니다.
    - PDF 파일의 경우 extract_text로 텍스트를 추출합니다.
    - URL의 경우 BeautifulSoup을 이용해 HTML에서 텍스트를 추출합니다.
    - 지원하지 않는 형식이면 해당 메시지를 반환합니다.
    """
    if os.path.exists(source):
        if source.lower().endswith(".txt"):
            try:
                with open(source, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"텍스트 파일 읽기 실패: {e}"
        elif source.lower().endswith(".pdf"):
            try:
                pdf_text = extract_text(source)
                return pdf_text
            except Exception as e:
                return f"PDF 파일 읽기 실패: {e}"
        else:
            return "지원하지 않는 파일 형식입니다."
    elif source.startswith("http://") or source.startswith("https://"):
        try:
            response = requests.get(source)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                return soup.get_text(separator="\n").strip()
            else:
                return f"URL 응답 실패: 상태코드 {response.status_code}"
        except Exception as e:
            return f"URL 접근 실패: {e}"
    else:
        return "관련 문서 요약: ...검색된 문서 내용..."

class OllamaClientChatBot:
    """
    OllamaClientChatBot 클래스:
    - Ollama API와 연동해서 챗봇 대화를 처리합니다.
    - 옵션에 따라 RAG(관련 정보 검색) 기능을 사용하여 추가 문맥 정보를 포함할 수 있습니다.
    """
    def __init__(self, model, system_prompt, max_history, use_rag=False, rag_source: str = None):
        # 챗봇 초기 설정: 모델명, 시스템 프롬프트, 최대 대화 기록, RAG 사용 여부, RAG 소스 등
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.use_rag = use_rag
        self.rag_source = rag_source
        self.client = Client(host="http://localhost:11434")
        # 대화 기록 초기화 (system 메시지로 시작)
        self.messages = [{"role": "system", "content": system_prompt}]

    def _trim_history(self):
        """대화 기록을 최대 히스토리 크기로 제한합니다."""
        if len(self.messages) > self.max_history * 2 + 1:
            # 가장 초반의 system 메시지와 최근 max_history 이하의 대화만 남깁니다.
            self.messages = [self.messages[0]] + self.messages[-(self.max_history * 2):]

    def stream_chat(self, user_input: str) -> Generator[str, None, None]:
        """
        사용자 입력을 받아 챗봇의 응답을 스트리밍 형식으로 제공합니다.
        - RAG가 활성화된 경우, 먼저 문맥 정보를 retrieve_context로 가져와 사용자 입력 앞에 추가합니다.
        - 생성된 응답 조각들을 하나씩 yield합니다.
        """
        if self.use_rag and self.rag_source and any(kw in user_input for kw in ["문서", "정보"]):
            context = retrieve_context(self.rag_source)
            user_input = f"{context}\n\n{user_input}"
        
        # 사용자 메시지를 대화 기록에 추가
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
            # 모든 응답을 하나로 합쳐 대화 기록에 저장 후, 기록 정리
            self.messages.append({"role": "assistant", "content": "".join(full_response)})
            self._trim_history()
        except Exception as e:
            yield f"\n[ERROR: {str(e)}]"

def recognize_speech_from_mic(recognizer, microphone):
    """
    마이크로부터 음성을 입력받고, Google Speech Recognition API를 이용해 텍스트로 변환합니다.
    - 주의: 음성이 인식되지 않거나 API 접근 실패 시 None을 반환합니다.
    """
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
    # 음성 인식에 사용할 Recognizer와 Microphone 초기화
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    # RAG 소스로 사용될 로컬 폴더 및 URL 목록
    rag_source = [
        "d:/Develops/Ollama/documents/",
        "https://namu.wiki/w/%EC%96%B8%EC%96%B4%20%EB%AA%A8%EB%8D%B8"
    ]
    
    # 챗봇 인스턴스 생성(모델, 시스템 프롬프트, 대화 기록 최대 크기, RAG 사용 여부, RAG 소스 설정)
    bot = OllamaClientChatBot(
        model="exaone3.5:2.4b-instruct-q4_K_M",
        system_prompt="저는 인공지능 보조 비서입니다. 한국어로 간결하게 대답하며, 이모티콘은 사용하지 않습니다.",
        max_history=3,
        use_rag=True,
        rag_source=rag_source
    )

    # rich 라이브 콘솔을 사용해 대화 인터페이스 출력 준비
    console = Console()
    console.print("챗봇을 시작합니다 (종료: '종료'라고 말하세요)")

    while True:
        try:
            # 음성 입력을 텍스트로 변환
            user_input = recognize_speech_from_mic(recognizer, microphone)
            if user_input is None:
                continue

            console.print(f"\nYou: {user_input}")
            if user_input.lower() in ["종료", "끝", "대화 종료"]:
                console.print("대화를 종료합니다.")
                break

            response_chunks = []
            # 챗봇 응답을 스트리밍으로 받아옴
            for chunk in bot.stream_chat(user_input):
                response_chunks.append(chunk)

            full_response = "".join(response_chunks)

            # TTS API 호출: 합성된 음성 파일의 경로를 받음
            response = requests.post("http://127.0.0.1:5000/synthesize", json={"text": full_response, "language": "ko"})
            if response.status_code == 200:
                temp_AUDIO_PATH = response.json()["audio_path"]
            else:
                console.print("TTS synthesis failed.")
                continue
            
            # 오디오 재생을 위해 음성 파일의 길이를 가져옴
            with wave.open(temp_AUDIO_PATH, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)

            # pygame 모듈을 이용해 음성 파일을 재생할 준비를 함
            pygame.mixer.init()
            pygame.mixer.music.load(temp_AUDIO_PATH)

            # 챗봇 응답 텍스트를 토큰 단위로 분리하여 재생 시간과 매핑
            tokens = re.findall(r'\S+|\s+', full_response)
            num_tokens = len(tokens)
            time_per_token = duration / num_tokens if num_tokens > 0 else 0

            # 줄 단위로 구분 (각 줄의 재생 타이밍을 계산하기 위함)
            lines = full_response.split('\n')
            tokens_per_line = [re.findall(r'\S+|\s+', line) for line in lines]
            num_tokens_per_line = [len(tokens) for tokens in lines]

            # 각 줄의 시작 시간과 종료 시간 계산
            start_times = [0] * len(lines)
            end_times = [0] * len(lines)
            cumulative_tokens = 0
            for i in range(len(lines)):
                num_tokens_line = num_tokens_per_line[i]
                start_times[i] = cumulative_tokens * time_per_token
                end_times[i] = start_times[i] + num_tokens_line * time_per_token
                cumulative_tokens += num_tokens_line

            def full_response_up_to_current_time(current_line_index, current_time):
                """
                현재 재생 시간을 기준으로, 진행된 텍스트(전체 또는 일부)를 반환하는 함수입니다.
                - 완료된 줄과 진행 중인 줄의 일부를 포함하여 사용자에게 진행 상황을 보여줌
                """
                text = ""
                for i in range(current_line_index):
                    text += lines[i] + '\n'
                if current_line_index < len(lines):
                    time_elapsed_in_current_line = current_time - start_times[current_line_index]
                    tokens_in_current_line = tokens_per_line[current_line_index]
                    num_tokens_to_print = int(time_elapsed_in_current_line / time_per_token)
                    num_tokens_to_print = min(num_tokens_to_print, len(tokens_in_current_line))
                    partial_line_text = "".join(tokens_in_current_line[:num_tokens_to_print])
                    text += partial_line_text
                else:
                    text += lines[-1]
                return text

            # 라이브 업데이트를 통해 챗봇 응답 텍스트와 재생 진행 상황을 출력함
            with Live(auto_refresh=True, console=console, transient=False) as live:
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    current_time = pygame.mixer.music.get_pos() / 1000
                    current_line_index = 0
                    while current_line_index < len(lines) and current_time >= end_times[current_line_index]:
                        current_line_index += 1
                    current_line_index = min(current_line_index, len(lines) - 1)
                    
                    printed_text = "Bot: " + full_response_up_to_current_time(current_line_index, current_time)
                    live.update(printed_text)
                    time.sleep(0.01)
                live.update("Bot: " + full_response)
            time.sleep(1)
            
        except KeyboardInterrupt:
            console.print("\n대화를 종료합니다.")
            break
