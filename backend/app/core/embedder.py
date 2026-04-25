import numpy as np
from typing import Optional


_instance: Optional["Embedder"] = None


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self._model_name = model_name
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        from FlagEmbedding import BGEM3FlagModel
        try:
            self._model = BGEM3FlagModel(self._model_name, use_fp16=True)
        except Exception:
            self._model = BGEM3FlagModel(self._model_name, use_fp16=False)

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
