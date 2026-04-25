"""
BGE-M3 embedding modülü.
Dense + Sparse vektör üretimi.

Model: BAAI/bge-m3 (568M parametre, 1024 boyutlu dense çıktı)
Kütüphane: FlagEmbedding

ÖNEMLİ: Bu sınıftan SADECE BİR TANE oluştur (Singleton pattern).
"""

from FlagEmbedding import BGEM3FlagModel


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
        """
        BGE-M3 modelini yükler.

        Args:
            model_name: Hugging Face model adı.
            use_fp16: True = yarım hassasiyet (16-bit float).
                      Bellek tüketimini %50 azaltır.
                      Doğruluk kaybı ihmal edilebilir düzeyde.
                      8GB RAM'de ZORUNLU, 16GB'de önerilen.
        """
        self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
        self.model_name = model_name

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
        # FlagEmbedding boş listede crash ettiği için erken dönüş yapıyoruz.
        if not texts:
            return {"dense": [], "sparse": []}

        embeddings = self.model.encode(
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
