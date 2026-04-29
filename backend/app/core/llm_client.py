"""
LLM istemci modülü.
Groq ve Google Gemini desteği.
Sağlayıcı .env'deki LLM_PROVIDER ile seçilir.

Tasarım prensibi:
- BaseLLMClient abstract class → ortak arayüz
- Her sağlayıcı için ayrı class → GroqClient, GeminiClient
- create_llm_client() factory → .env'den provider'ı okur, uygun client'ı döner
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

# =========================================================================
# RAG PROMPT ŞABLONLARI
# =========================================================================
# LLM'e gönderilecek system prompt — kuralları burada tanımlıyoruz.
# Düşük temperature (0.1) ile birlikte bu kurallar halüsilnasyonu minimize eder.

SYSTEM_PROMPT = """Sen bir doküman asistanısın. Görevin, kullanıcının yüklediği belgeler
üzerinden soruları doğru ve net bir şekilde yanıtlamaktır.

KURALLAR:
1. YALNIZCA aşağıda verilen kaynaklardaki bilgilere dayanarak cevap ver.
2. Eğer kaynaklar soruyu cevaplamak için yeterli değilse, bunu açıkça belirt.
   Asla bilgiyi uydurma veya tahmin yürütme.
3. Türkçe soru sorulursa Türkçe, İngilizce sorulursa İngilizce cevap ver.
4. Cevabın kısa ve öz olsun. Gereksiz tekrar yapma.
5. Cevabında asla "[KAYNAK ...]" gibi ibareler kullanma. Kaynak bilgisi ayrıca gösterilecektir."""

SUMMARY_SYSTEM_PROMPT = """Sen bir doküman özetleme asistanısın. Görevin, verilen metin
parçalarını kapsamlı ve doğru bir şekilde özetlemektir.

KURALLAR:
1. YALNIZCA verilen metinlerdeki bilgilere dayanarak özet oluştur.
2. Önemli detayları kaçırma ama gereksiz tekrar yapma.
3. Özet Türkçe yazılsın (metin Türkçe ise).
4. Bilgi uydurma, tahmin yürütme."""


def build_rag_prompt(question: str, context_chunks: list[dict]) -> str:
    """
    Kullanıcı sorusu ve parent chunk'ları birleştirerek
    LLM'e gönderilecek prompt'u oluşturur.

    ÖNEMLİ: LLM'e parent chunk'lar gönderilir, child değil.
    child aramada bulundu (yüksek precision), ama LLM'e
    geniş bağlamı olan parent verilir (zengin context).

    Args:
        question: Kullanıcının sorusu
        context_chunks: vector_store.get_parent_by_id() ile gelen parent chunk listesi

    Returns:
        LLM'e gönderilecek formatlı prompt
    """
    context_parts = []

    for i, chunk in enumerate(context_chunks, 1):
        source_info = chunk.get("metadata", {}).get("filename", "Bilinmeyen")
        page = chunk.get("metadata", {}).get("page_number")
        if page:
            source_info += f", Sayfa {page}"

        context_parts.append(f"[KAYNAK {i} — {source_info}]\n{chunk.get('text', '')}")

    context_text = "\n\n---\n\n".join(context_parts)

    return f"""Aşağıdaki kaynaklara dayanarak soruyu yanıtla.

{context_text}

---

SORU: {question}"""


# =========================================================================
# TEMEL LLM SINIFI (Abstract Base Class)
# =========================================================================


class BaseLLMClient(ABC):
    """
    Tüm LLM sağlayıcıları bu arayüzü uygular.
    Yeni sağlayıcı eklemek için bu sınıftan türet ve
    generate() + stream() metodlarını implemente et.
    """

    # Alt sınıflar kendi model adını bu attribute'a atamalı
    # (Langfuse trace'lerinde kullanılacak)
    model: str = ""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """Tek seferde tam cevap üretir (non-streaming)."""
        pass

    @abstractmethod
    async def stream(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> AsyncGenerator[str]:
        """Token token cevap akışı üretir (SSE için)."""
        pass


# =========================================================================
# GROQ İSTEMCİSİ
# =========================================================================


class GroqClient(BaseLLMClient):
    """
    Groq API üzerinden Llama 3.3 70B.
    280 TPS hız, $0.59/1M girdi tokeni.

    Kullanım:
        client = GroqClient(api_key="gsk_...")
        answer = await client.generate("soru nedir?", SYSTEM_PROMPT)
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        from groq import AsyncGroq

        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # Düşük = deterministik, halüsilnasyon az
            max_tokens=2048,
        )
        return response.choices[0].message.content

    async def stream(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> AsyncGenerator[str]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# =========================================================================
# GEMINI İSTEMCİSİ
# =========================================================================


class GeminiClient(BaseLLMClient):
    """
    Google Gemini 2.5 Flash.
    1M token context window, $0.30/1M girdi tokeni.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai_model = genai.GenerativeModel(model)
        self.model = model

    async def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        # Gemini ayrı system_prompt kavramı yok, birleştiriyoruz
        full_prompt = f"{system_prompt}\n\n{prompt}"
        response = await self._genai_model.generate_content_async(
            full_prompt, generation_config={"temperature": 0.1, "max_output_tokens": 2048}
        )
        return response.text

    async def stream(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> AsyncGenerator[str]:
        full_prompt = f"{system_prompt}\n\n{prompt}"
        response = await self._genai_model.generate_content_async(
            full_prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 2048},
            stream=True,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text


# =========================================================================
# FACTORY — Sağlayıcı seçici
# =========================================================================


def create_llm_client(provider: str, api_key: str, model: str = "") -> BaseLLMClient:
    """
    .env'deki LLM_PROVIDER değerine göre uygun istemciyi döndürür.

    Args:
        provider: "groq" veya "google"
        api_key: API anahtarı
        model: Özel model adı (boş ise provider'a göre varsayılan kullanılır)

    Returns:
        BaseLLMClient: İstenen sağlayıcıya ait client instance'ı

    Raises:
        ValueError: Desteklenmeyen provider adı
    """
    match provider.lower():
        case "groq":
            return GroqClient(api_key, model or "llama-3.3-70b-versatile")
        case "google":
            return GeminiClient(api_key, model or "gemini-2.5-flash")
        case _:
            raise ValueError(
                f"Desteklenmeyen LLM sağlayıcı: {provider}. Desteklenen: 'groq', 'google'"
            )
