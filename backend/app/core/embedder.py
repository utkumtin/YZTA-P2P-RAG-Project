"""
BGE-M3 embedding modülü.
Dense + Sparse vektör üretimi.

Model: BAAI/bge-m3 (568M parametre, 1024 boyutlu dense çıktı)
Kütüphane: FlagEmbedding

ÖNEMLİ: Bu sınıftan SADECE BİR TANE oluştur (Singleton pattern).
"""

import numpy as np
from typing import Optional

_instance: Optional["Embedder"] = None


class Embedder:
    """
    BGE-M3 ile metin → vektör dönüşümü.

    Kullanım:
        embedder = Embedder()  # Model ilk seferde indirilir (~1.7GB)

        # Birden fazla metin (ingestion sırasında)
        result = embedder.encode(["metin 1", "metin 2", "metin 3"])
        dense_vecs = result["dense"]     # [[float×1024], [float×1024], ...]
        sparse_vecs = result["sparse"]   # [{token_id: weight}, ...]

        # Tek soru (query sırasında)
        q = embedder.encode_query("soru nedir?")
        q_dense = q["dense"]    # [float×1024]
        q_sparse = q["sparse"]  # {token_id: weight}
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        use_fp16: bool = True,
    ):
        self._model_name = model_name
        self._use_fp16 = use_fp16
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        from FlagEmbedding import BGEM3FlagModel
        try:
            self._model = BGEM3FlagModel(self._model_name, use_fp16=self._use_fp16)
        except Exception:
            self._model = BGEM3FlagModel(self._model_name, use_fp16=False)

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> dict:
        """
        Metin listesini dense + sparse vektörlere dönüştürür.

        Args:
            texts: Embedding üretilecek metin listesi.
                   BOŞ LİSTE GEÇİLMEMELİ — FlagEmbedding hata verir,
                   bu yüzden erken dönüş yapıyoruz.
            batch_size: Bellek taşması önlemek için batch boyutu.
                        32 = güvenli varsayılan.
                        GPU 24GB+ varsa 64'e çıkabilirsin.
                        8GB RAM varsa 16'ya düşür.

        Returns:
            dict: {
                "dense": list[list[float]],  # Her metin için 1024 boyutlu vektör
                "sparse": list[dict]         # Her metin için {token_id: weight} sözlüğü
            }
        """
        self._load()
        # FlagEmbedding boş listede crash ettiği için erken dönüş yapıyoruz.
        if not texts:
            return {"dense": [], "sparse": []}

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,  # ColBERT şu an kullanılmıyor (performans için kapalı)
        )

        # numpy array → Python list dönüşümü (JSON serialization için gerekli)
        dense = (
            embeddings["dense_vecs"].tolist()
            if hasattr(embeddings["dense_vecs"], "tolist")
            else embeddings["dense_vecs"]
        )

        return {
            "dense": dense,
            "sparse": embeddings["lexical_weights"],
        }

    def encode_query(self, query: str) -> dict:
        """
        Tek bir sorguyu encode eder.
        Kullanıcı soru sorduğunda bu metod çağrılır.

        Args:
            query: Kullanıcının sorusu.

        Returns:
            dict: {
                "dense": list[float],     # Tek bir 1024 boyutlu vektör
                "sparse": dict            # Tek bir {token_id: weight} sözlüğü
            }
        """
        result = self.encode([query], batch_size=1)
        return {
            "dense": result["dense"][0],
            "sparse": result["sparse"][0],
        }

    def embed(self, text: str) -> np.ndarray:
        self._load()
        result = self._model.encode([text], batch_size=1)
        return result["dense_vecs"][0].astype(np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        self._load()
        result = self._model.encode(texts, batch_size=32)
        return result["dense_vecs"].astype(np.float32)


def get_embedder() -> Embedder:
    global _instance
    if _instance is None:
        _instance = Embedder()
    return _instance
