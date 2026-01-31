import whisper
import warnings
import sys

warnings.filterwarnings('ignore')

voice_file = r'D:\coder\myagent\data\media\telegram\voice_AwACAgUAAxkBAAIBoml-DP7m9oMggIcRL15AtWafj_BtAAJzHQACXYHwV-ReZS1Myh3pOAQ.ogg'

try:
    print("正在加载语音识别模型...")
    model = whisper.load_model('base')
    
    print("正在识别语音内容...")
    result = model.transcribe(voice_file, language='zh')
    
    print("=" * 50)
    print("【语音识别结果】")
    print(result['text'])
    print("=" * 50)
except Exception as e:
    print(f"识别出错: {e}")
