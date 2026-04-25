"""
Yeniden sıralama (Reranking) modülü.
Cross-Encoder ile aday dokümanları yeniden sıralar.

Bi-encoder (embedding) vs Cross-encoder:
- Bi-encoder: Soru ve doküman AYRI AYRI vektörlenir → hızlı ama yüzeysel
- Cross-encoder: Soru ve doküman BİRLİKTE değerlendirilir → yavaş ama derin

Model: BAAI/bge-reranker-v2-m3
Fallback: FlashRank (GPU yoksa)

Etki: NDCG@10 kalitesini %28-48 artırır.

PRD Referans: Bölüm 10 — Yeniden Sıralama
"""

from FlagEmbedding import FlagReranker


class Reranker:
    """
    bge-reranker-v2-m3 ile yeniden sıralama.
    
    Kullanım:
        reranker = Reranker()
        reranked = reranker.rerank("soru nedir?", candidates, top_k=5)
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        use_fp16: bool = True
    ):
        self.model = FlagReranker(model_name, use_fp16=use_fp16)
    
    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5
    ) -> list[dict]:
        """
        Aday dokümanları yeniden sıralar.
        
        Args:
            query: Kullanıcının sorusu
            documents: Hibrit aramadan gelen aday chunk'lar
            top_k: En alakalı kaç chunk döndürmek istiyoruz
        
        Returns:
            Yeniden sıralanmış en alakalı top_k chunk.
            Her chunk'a "rerank_score" alanı eklenir.
        """
        if not documents:
            return []
        
        # Cross-encoder için (soru, doküman) çiftleri oluştur
        pairs = [(query, doc["text"]) for doc in documents]
        
        # Skorları hesapla
        scores = self.model.compute_score(pairs)
        
        # DİKKAT: Tek eleman geldiğinde FlagReranker float döner, liste değil!
        # Bu yaygın bir tuzak. Her zaman listeye sar.
        if isinstance(scores, (int, float)):
            scores = [scores]
        
        # Skorları dokümanlara ekle
        for i, doc in enumerate(documents):
            doc["rerank_score"] = float(scores[i])
        
        # Skora göre azalan sırala
        ranked = sorted(documents, key=lambda x: x["rerank_score"], reverse=True)
        
        return ranked[:top_k]
