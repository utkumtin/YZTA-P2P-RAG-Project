"""FAZ 8 testleri — LLM istemcileri"""
import pytest

from app.core.llm_client import create_llm_client, SYSTEM_PROMPT, build_rag_prompt

def test_factory_creates_correct_client():
    # Test 1: Factory fonksiyonu
    client = create_llm_client("groq", "dummy_key")
    assert client.model == "llama-3.3-70b-versatile"

def test_factory_raises_value_error_for_invalid_provider():
    # Test 2: Desteklenmeyen provider → hata
    with pytest.raises(ValueError, match="Desteklenmeyen LLM sağlayıcı"):
        create_llm_client("azure", "dummy")

def test_build_rag_prompt_format():
    # Test 5: build_rag_prompt formatı
    chunks = [
        {"text": "Kira bedeli 5000 TL.", "metadata": {"filename": "a.pdf", "page_number": 3}},
        {"text": "Fesih 30 gün önceden.", "metadata": {"filename": "a.pdf", "page_number": 7}}
    ]
    prompt = build_rag_prompt("Kira ne kadar?", chunks)
    assert "[KAYNAK 1" in prompt
    assert "Sayfa 3" in prompt
    assert "SORU: Kira ne kadar?" in prompt
