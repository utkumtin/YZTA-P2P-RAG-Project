import json
import base64
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from app.core.embedder import Embedder


class SemanticCache:
    def __init__(
        self,
        redis_client,
        embedder: Embedder,
        threshold: float = 0.92,
        ttl: int = 3600,
        max_size: int = 1000,
    ):
        self._redis = redis_client
        self._embedder = embedder
        self._threshold = threshold
        self._ttl = ttl
        self._max_size = max_size
        self._index: dict[str, np.ndarray] = {}
        self._meta: dict[str, dict] = {}

    async def load_from_redis(self):
        try:
            keys = []
            async for key in self._redis.scan_iter("sc:*"):
                keys.append(key)
            for key in keys:
                raw = await self._redis.get(key)
                if raw is None:
                    continue
                entry = json.loads(raw)
                vec = np.frombuffer(base64.b64decode(entry["embedding_b64"]), dtype=np.float32)
                short_key = key.decode() if isinstance(key, bytes) else key
                self._index[short_key] = vec
                self._meta[short_key] = {
                    "response": entry["response"],
                    "created_at": entry["created_at"],
                }
        except Exception:
            pass

    async def get(self, query: str) -> Optional[dict]:
        if not self._index:
            return None
        try:
            query_vec = self._embedder.embed(query)
            best_key, best_score = self._find_best_match(query_vec)
            if best_score >= self._threshold:
                return self._meta[best_key]["response"]
        except Exception:
            pass
        return None

    async def set(self, query: str, response: dict) -> None:
        try:
            if len(self._index) >= self._max_size:
                await self._evict_oldest()
            query_vec = self._embedder.embed(query)
            key = f"sc:{uuid.uuid4().hex}"
            entry = {
                "query": query,
                "response": response,
                "embedding_b64": base64.b64encode(query_vec.tobytes()).decode(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._redis.set(key, json.dumps(entry), ex=self._ttl)
            self._index[key] = query_vec
            self._meta[key] = {
                "response": response,
                "created_at": entry["created_at"],
            }
        except Exception:
            pass

    async def clear(self) -> None:
        try:
            keys = list(self._index.keys())
            if keys:
                await self._redis.delete(*keys)
            self._index.clear()
            self._meta.clear()
        except Exception:
            pass

    def _find_best_match(self, query_vec: np.ndarray) -> tuple[str, float]:
        best_key = ""
        best_score = -1.0
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return best_key, best_score
        for key, vec in self._index.items():
            v_norm = np.linalg.norm(vec)
            if v_norm == 0:
                continue
            score = float(np.dot(query_vec, vec) / (q_norm * v_norm))
            if score > best_score:
                best_score = score
                best_key = key
        return best_key, best_score

    async def _evict_oldest(self) -> None:
        if not self._meta:
            return
        oldest_key = min(self._meta, key=lambda k: self._meta[k]["created_at"])
        try:
            await self._redis.delete(oldest_key)
        except Exception:
            pass
        self._index.pop(oldest_key, None)
        self._meta.pop(oldest_key, None)
