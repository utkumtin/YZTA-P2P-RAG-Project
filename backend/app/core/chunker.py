"""
Parent-Child chunker modülü.

Mantık:
- Parent: 800 token, geniş bağlam → LLM'e gönderilir
- Child: 200 token, spesifik bilgi → Vektör aramasında kullanılır
- Arama child'da yapılır, LLM'e parent gönderilir

ID Formatı:
- Parent: "parent-{doc_id}-{sıra_no}"        → "parent-abc123-0001"
- Child:   "child-{doc_id}-{parent_index}-{child_index}" → "child-abc123-0001-002"
"""

import uuid

import tiktoken
from llama_index.core.node_parser import SentenceSplitter

# Token encoder: cl100k_base
_enc = tiktoken.get_encoding("cl100k_base")


def _token_length(text: str) -> int:
    """
    Metnin token sayısını döndürür.

    Args:
        text: Token sayısı ölçülecek metin

    Returns:
        int: Token sayısı
    """
    return len(_enc.encode(text))


def create_parent_child_chunks(
    full_text: str,
    doc_metadata: dict,
    parent_chunk_size: int = 800,
    parent_chunk_overlap: int = 100,
    child_chunk_size: int = 200,
    child_chunk_overlap: int = 50,
    pages: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Metni Parent-Child stratejisiyle parçalar.

    Bu fonksiyonun iki aşamalı mantığı:

    AŞAMA 1 — Parent parçalar (800 token):
        Dokümanı büyük bloklara ayırır. Her blok bir konunun bütünsel
        bağlamını taşır. Bunlar LLM'e gönderilecek nihai metin parçalarıdır.

    AŞAMA 2 — Child parçalar (200 token, her parent'tan):
        Her parent kendi içinde daha küçük parçalara bölünür.
        Bu küçük parçalar vektörleştirilir ve Qdrant'ta saklanır.
        Kullanıcı soru sorduğunda child parçalarda arama yapılır,
        bulunan çocuğun parent LLM'e gönderilir.

    Neden bu strateji?
        Küçük chunk (child) → Yüksek precision (doğru parçayı bulur)
        Büyük chunk (parent) → Zengin bağlam (LLM doğru cevap üretir)

    Args:
        full_text: Temizlenmiş doküman metni (text_cleaner.clean_text çıktısı)
        doc_metadata: Doküman seviyesi metadata. Zorunlu alanlar:
            {
                "doc_id": str,       # UUID (ör: "550e8400-e29b-41d4-...")
                "filename": str,     # "sozlesme.pdf"
                "file_type": str,    # "pdf", "docx", "doc", "txt"
                "language": str,     # "tr", "en", "unknown"
                "session_id": str    # Kullanıcı oturumu
            }
        parent_chunk_size: Parent parça boyutu (token). Varsayılan: 800
        parent_chunk_overlap: Parent parçalar arası örtüşme (token). Varsayılan: 100
        child_chunk_size: Child parça boyutu (token). Varsayılan: 200
        child_chunk_overlap: Child parçalar arası örtüşme (token). Varsayılan: 50
        pages: Sayfa-başına chunking için [{"page_number": int, "text": str}, ...].
               Verilirse her chunk kendi sayfasının page_number'ını taşır.
               None ise full_text üzerinden standart davranış (page_number atanmaz).

    Returns:
        tuple: (parent_chunks, child_chunks)

        Her parent_chunk:
        {
            "id": "parent-{doc_id}-0001",
            "text": "parent metin...",
            "metadata": {
                ...doc_metadata,         # doc_id, filename, file_type, language, session_id
                "chunk_type": "parent",
                "chunk_index": 0         # 0-indexed sıra numarası
            }
        }

        Her child_chunk:
        {
            "id": "child-{doc_id}-0001-000",
            "text": "child metin...",
            "metadata": {
                ...doc_metadata,
                "chunk_type": "child",
                "chunk_index": 0,                    # Parent içindeki sıra (0-indexed)
                "parent_chunk_id": "parent-{doc_id}-0001"  # Hangi parent'a ait
            }
        }

    Raises:
        ValueError: full_text boş veya None ise
    """
    if not pages and (not full_text or not full_text.strip()):
        raise ValueError("full_text boş olamaz. Chunking için metin gerekli.")

    # doc_id yoksa UUID üret (fallback — normalde backend'ci sağlamalı)
    doc_id = doc_metadata.get("doc_id") or str(uuid.uuid4())

    # LlamaIndex SentenceSplitter Yapılandırması
    # chunk_size:          Maximum token sayısı (bu eşiği geçmez)
    # chunk_overlap:       Parçalar arasında tekrarlanan token miktarı
    #                      Konu geçişlerinde bilgi kaybını önler
    # tokenizer:           Token sayımı için kullandığı fonksiyon
    #                      _enc.encode → tiktoken cl100k_base encoder
    # paragraph_separator: Önce paragraf sınırlarına göre böl
    #                      \n\n → clean_text'in ürettiği paragraf ayırıcı
    # separator:           Paragraf sınırında kesilmek zorundaysa kelime sınırı
    # Bölünme hiyerarşisi:
    #   1. \n\n  → Paragraf sınırı (tercih edilen)
    #   2. \n    → Satır sonu
    #   3. " "   → Kelime sınırı (son çare)

    # Parent chunker (büyük bloklar — geniş bağlam)
    parent_splitter = SentenceSplitter(
        chunk_size=parent_chunk_size,
        chunk_overlap=parent_chunk_overlap,
        tokenizer=_enc.encode,
        paragraph_separator="\n\n",
        separator=" ",
    )

    # Child chunker (küçük bloklar — spesifik bilgi, yüksek precision)
    child_splitter = SentenceSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        tokenizer=_enc.encode,
        paragraph_separator="\n\n",
        separator=" ",
    )

    parent_chunks: list[dict] = []
    child_chunks: list[dict] = []

    # pages verilmişse her sayfayı ayrı chunkla — her chunk kendi page_number'ını taşır
    if pages:
        chunk_counter = 0
        for page in pages:
            page_text = page["text"]
            page_number = page["page_number"]
            if not page_text.strip():
                continue

            for parent_text in parent_splitter.split_text(page_text):
                parent_id = f"parent-{doc_id}-{chunk_counter:04d}"
                parent_chunks.append(
                    {
                        "id": parent_id,
                        "text": parent_text,
                        "metadata": {
                            **doc_metadata,
                            "chunk_type": "parent",
                            "chunk_index": chunk_counter,
                            "page_number": page_number,
                        },
                    }
                )

                for j, child_text in enumerate(child_splitter.split_text(parent_text)):
                    child_chunks.append(
                        {
                            "id": f"child-{doc_id}-{chunk_counter:04d}-{j:03d}",
                            "text": child_text,
                            "metadata": {
                                **doc_metadata,
                                "chunk_type": "child",
                                "chunk_index": j,
                                "parent_chunk_id": parent_id,
                                "page_number": page_number,
                            },
                        }
                    )

                chunk_counter += 1
        return parent_chunks, child_chunks

    # ─────────────────────────────────────────────────────────────────────────
    # AŞAMA 1: Parent parçalar oluştur (pages verilmediğinde — backward compat)
    # ─────────────────────────────────────────────────────────────────────────
    parent_texts = parent_splitter.split_text(full_text)

    for i, parent_text in enumerate(parent_texts):
        # Parent ID: "parent-{doc_id}-{sıra_no 4 basamak}"
        # Örnek: "parent-550e8400-0003"
        parent_id = f"parent-{doc_id}-{i:04d}"

        parent_chunks.append(
            {
                "id": parent_id,
                "text": parent_text,
                "metadata": {
                    **doc_metadata,  # doc_id, filename, file_type, language, session_id
                    "chunk_type": "parent",
                    "chunk_index": i,
                },
            }
        )

        # ─────────────────────────────────────────────────────────────────────
        # AŞAMA 2: Bu parent'tan child parçalar oluştur
        # Sadece bu parent'ın metnini böl. Tüm dokümanı değil!
        # Bu sayede her child kesin olarak kendi parent'ının altında kalır.
        # ─────────────────────────────────────────────────────────────────────
        child_texts = child_splitter.split_text(parent_text)

        for j, child_text in enumerate(child_texts):
            # Child ID: "child-{doc_id}-{parent_index}-{child_index}"
            # Örnek: "child-550e8400-0003-002"
            child_id = f"child-{doc_id}-{i:04d}-{j:03d}"

            child_chunks.append(
                {
                    "id": child_id,
                    "text": child_text,
                    "metadata": {
                        **doc_metadata,
                        "chunk_type": "child",
                        "chunk_index": j,
                        "parent_chunk_id": parent_id,  # Hangi parent'a → retrieval'da kritik
                    },
                }
            )

    return parent_chunks, child_chunks
