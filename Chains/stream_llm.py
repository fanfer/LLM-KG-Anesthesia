from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
import os
from web.stream_tts import StreamTTSHandler

def get_streaming_llm(callbacks=None, model="gpt-4o", temperature=0.6, max_tokens=None):
    """获取支持流式输出的LLM
    
    Args:
        callbacks: 回调函数列表，用于处理流式输出
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数
        
    Returns:
        支持流式输出的LLM
    """
    # 创建LLM参数
    llm_kwargs = {
        "model": model,
        "temperature": temperature,
        "streaming": True,
    }
    
    # 如果指定了最大token数，则添加到参数中
    if max_tokens is not None:
        llm_kwargs["max_tokens"] = max_tokens
    
    # 如果指定了回调函数，则添加到参数中
    if callbacks is not None:
        llm_kwargs["callbacks"] = callbacks
    else:
        llm_kwargs["callbacks"] = [create_stream_tts_handler()]
    
    # 创建LLM
    if "gpt" in model or "openai" in model:
        return ChatOpenAI(**llm_kwargs)
    else:
        # 使用Ollama模型
        llm_kwargs["base_url"] = "http://222.20.98.120:11434"
        return ChatOllama(**llm_kwargs)

def create_stream_tts_handler(callback=None):
    """创建流式TTS处理器
    
    Args:
        callback: 回调函数，用于将音频数据发送给前端
        
    Returns:
        流式TTS处理器
    """
    # 从环境变量中获取讯飞API的配置
    app_id = os.environ.get("XUNFEI_APP_ID", "0fd3127e")
    api_key = os.environ.get("XUNFEI_API_KEY", "22c490aacbd823d6cb89dced0a711e09")
    api_secret = os.environ.get("XUNFEI_API_SECRET", "YzM0Nzk3ZDgzOWYxYjBiZGRkYmZiMzc2")
    
    # 创建流式TTS处理器
    return StreamTTSHandler(app_id=app_id, api_key=api_key, api_secret=api_secret, callback=callback) 