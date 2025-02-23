import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")

import logging
logging.getLogger("transformers").setLevel(logging.ERROR)
try:
    from transformers import logging as hf_logging
    hf_logging.set_verbosity_error()
except ImportError:
    pass

import os
# tqdm 진행률 바를 비활성화 (만약 tqdm를 사용하는 경우)
os.environ["TQDM_DISABLE"] = "True"

import warnings
warnings.filterwarnings("ignore", message="stft with return_complex=False is deprecated")
warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub.file_download")

import torch
import nltk
from openvoice import se_extractor
from openvoice.api import ToneColorConverter

ckpt_converter = 'library/OpenVoice/checkpoints_v2/converter'
device = "cuda:0" if torch.cuda.is_available() else "cpu"
output_dir = 'outputs_v2'
nltk.download('averaged_perceptron_tagger_eng', quiet=True)

tone_color_converter = ToneColorConverter(f'{ckpt_converter}/config.json', device=device)
tone_color_converter.load_ckpt(f'{ckpt_converter}/checkpoint.pth')
os.makedirs(output_dir, exist_ok=True)
reference_speaker = 'library/OpenVoice/resources/miku_reference.mp3'
target_se, audio_name = se_extractor.get_se(reference_speaker, tone_color_converter, vad=False)

def test():
    from melo.api import TTS
    texts = {
        'EN_NEWEST': "Hello, I'm Miku Hatsune. Nice to meet you.",  # The newest English base speaker model
        'EN': "Hello, I'm Miku Hatsune. Nice to meet you.",
        'JP': "こんにちは。初音ミクと申します。 よろしくお願いします.",
        'KR': "안녕하세요. 하츠네 미쿠라고 합니다. 잘 부탁드려요.",
    }

    src_path = f'{output_dir}/tmp.wav'
    speed = 1.0

    for language, text in texts.items():
        model = TTS(language=language, device=device)
        speaker_ids = model.hps.data.spk2id

        for speaker_key in speaker_ids.keys():
            speaker_id = speaker_ids[speaker_key]
            speaker_key = speaker_key.lower().replace('_', '-')

            source_se = torch.load(f'library/OpenVoice/checkpoints_v2/base_speakers/ses/{speaker_key}.pth', map_location=device)
            model.tts_to_file(text, speaker_id, src_path, speed=speed)
            save_path = f'{output_dir}/output_v2_{speaker_key}.wav'

            # Run the tone color converter
            encode_message = "@MyShell"
            tone_color_converter.convert(
                audio_src_path=src_path,
                src_se=source_se,
                tgt_se=target_se,
                output_path=save_path,
                message=encode_message)
            
def synthesize_speech(text: str, language: str = 'ko') -> str:
    """
    Synthesize speech for the given text.
    Returns the path to the synthesized audio file.
    """
    import time
    import os
    import torch
    from melo.api import TTS

    # Map the language parameter to the model's expected language key.
    lang_map = {'ko': 'KR', 'en': 'EN', 'jp': 'JP'}
    lang_key = lang_map.get(language.lower(), language.upper())

    model = TTS(language=lang_key, device=device)
    speaker_ids = model.hps.data.spk2id

    # Use the first available speaker
    speaker_key = list(speaker_ids.keys())[0]
    speaker_id = speaker_ids[speaker_key]
    speaker_key_mod = speaker_key.lower().replace("_", "-")

    # Load the source speaker embedding.
    source_se = torch.load(f'library/OpenVoice/checkpoints_v2/base_speakers/ses/{speaker_key_mod}.pth', map_location=device)

    # Prepare temporary file path (fixed)
    src_path = f'{output_dir}/tmp.wav'
    speed = 1.0

    # Synthesize audio to the temporary file.
    model.tts_to_file(text, speaker_id, src_path, speed=speed)

    # Generate a unique file name for the final output
    unique_suffix = int(time.time() * 1000)
    save_path = f'{output_dir}/output_v2_{speaker_key_mod}_{unique_suffix}.wav'

    # Run the tone color conversion.
    encode_message = "@MyShell"
    tone_color_converter.convert(
        audio_src_path=src_path,
        src_se=source_se,
        tgt_se=target_se,
        output_path=save_path,
        message=encode_message
    )

    # 요청이 완료된 후 임시 파일(tmp.wav) 삭제
    try:
        if os.path.exists(src_path):
            os.remove(src_path)
    except Exception as e:
        print(f"Error removing temporary file: {e}")

    return save_path

if __name__ == "__main__":
    test()