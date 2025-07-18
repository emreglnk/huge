import os
import google.generativeai as genai
from openai import AsyncOpenAI, OpenAIError
from .models import LlmConfig

# --- Client Initialization ---

clients = {}

# OpenAI
openai_api_key = os.environ.get("OPENAI_API_KEY")
if openai_api_key:
    clients["openai"] = AsyncOpenAI(api_key=openai_api_key)
else:
    print("WARNING: OPENAI_API_KEY not set. OpenAI models will be unavailable.")

# DeepSeek
deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
if deepseek_api_key:
    clients["deepseek"] = AsyncOpenAI(
        api_key=deepseek_api_key,
        base_url="https://api.deepseek.com/v1"
    )
else:
    print("WARNING: DEEPSEEK_API_KEY not set. DeepSeek models will be unavailable.")

# Gemini
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    clients["gemini"] = genai.GenerativeModel('gemini-pro')
else:
    print("WARNING: GEMINI_API_KEY not set. Gemini models will be unavailable.")

# --- LLM Response Generation ---

async def get_llm_response(llm_config: LlmConfig, system_prompt: str, user_message: str) -> str:
    provider = llm_config.provider
    model = llm_config.model

    if provider not in clients:
        return f"LLM provider '{provider}' is not configured or the API key is missing."

    try:
        if provider in ["openai", "deepseek"]:
            client = clients[provider]
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            return response.choices[0].message.content
        
        elif provider == "gemini":
            gemini_client = clients["gemini"]
            # Gemini uses a specific format for prompts
            full_prompt = f"{system_prompt}\n\nUser: {user_message}"
            response = await gemini_client.generate_content_async(full_prompt)
            return response.text

    except (OpenAIError, Exception) as e:
        print(f"Error calling {provider} API: {e}")
        return f"I'm sorry, but I encountered an error with the {provider} API."
