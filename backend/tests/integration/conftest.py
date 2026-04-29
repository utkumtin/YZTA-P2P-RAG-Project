"""
Integration test conftest — lokal ortamda kurulu olmayan ML/veritabanı
kütüphaneleri için sys.modules stub'ları. pytest bu dosyayı test modüllerini
toplamadan önce yükler, dolayısıyla module-level import'lar çalışır.
"""

import sys
import types
from unittest.mock import MagicMock

_EMPTY_MODULES = [
    "llama_index",
    "llama_index.core",
    "llama_index.core.node_parser",
    "llama_index.core.schema",
    "fitz",
    "docx",
    "langdetect",
    "FlagEmbedding",
    "surya",
    "surya.recognition",
    "surya.detection",
    "surya.layout",
    "surya.model",
    "qdrant_client",
    "qdrant_client.models",
    "qdrant_client.http",
    "qdrant_client.http.models",
]

for _mod_name in _EMPTY_MODULES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = types.ModuleType(_mod_name)

# llama_index stub'ları
if not hasattr(sys.modules["llama_index.core.node_parser"], "SentenceSplitter"):
    sys.modules["llama_index.core.node_parser"].SentenceSplitter = MagicMock

# docx stub
if not hasattr(sys.modules["docx"], "Document"):
    sys.modules["docx"].Document = type("Document", (), {"__init__": lambda *a, **k: None})

# langdetect stub
if not hasattr(sys.modules["langdetect"], "detect"):
    sys.modules["langdetect"].detect = lambda x: "tr"
    sys.modules["langdetect"].LangDetectException = Exception

# FlagEmbedding stub
_fe = sys.modules["FlagEmbedding"]
if not hasattr(_fe, "BGEM3FlagModel"):
    _fe.BGEM3FlagModel = type("BGEM3FlagModel", (), {"__init__": lambda *a, **k: None})
if not hasattr(_fe, "FlagReranker"):
    _fe.FlagReranker = type("FlagReranker", (), {"__init__": lambda *a, **k: None})

# qdrant_client stub'ları — vector_store.py'deki from qdrant_client.models import (...)
_qdrant_symbols = [
    "Distance", "FieldCondition", "Filter", "Fusion", "FusionQuery",
    "MatchAny", "MatchValue", "PayloadSchemaType", "PointStruct",
    "Prefetch", "SparseVector", "SparseVectorParams", "VectorParams",
    "VectorsConfig", "SparseVectorsConfig",
]
_qm = sys.modules["qdrant_client.models"]
for _sym in _qdrant_symbols:
    if not hasattr(_qm, _sym):
        setattr(_qm, _sym, type(_sym, (), {}))

_qc = sys.modules["qdrant_client"]
if not hasattr(_qc, "QdrantClient"):
    _qc.QdrantClient = type("QdrantClient", (), {"__init__": lambda *a, **k: None})
