import numpy as np
from app.config import EMBEDDING_DIM, QDRANT_PATH


class VectorService:
    def __init__(self):
        self.client = None
        self.collection_name = "students"
        self._init_client()

    def _init_client(self):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import VectorParams, Distance
            if QDRANT_PATH == ":memory:":
                self.client = QdrantClient(":memory:")
            else:
                self.client = QdrantClient(path=QDRANT_PATH)
            existing = self.client.get_collections()
            names = [c.name for c in existing.collections]
            if self.collection_name not in names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE,
                        on_disk=True,
                    ),
                )
            print(f"Qdrant ready (mode: {QDRANT_PATH})")
        except Exception as e:
            print(f"Qdrant init error: {e}")
            self.client = None

    @property
    def is_ready(self):
        return self.client is not None

    def upsert(self, uid: str, embedding: list, payload: dict):
        if self.client is None:
            return
        from qdrant_client.models import PointStruct
        point_id = abs(hash(uid)) % (2**63)
        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(id=point_id, vector=embedding, payload=payload)],
        )
        return point_id

    def search(self, embedding: list, limit: int = 1, score_threshold: float = 0.6):
        if self.client is None:
            return []
        from qdrant_client.models import Filter
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            limit=limit,
            score_threshold=score_threshold,
        )
        matches = []
        for r in results.points:
            matches.append({
                "uid": r.payload.get("uid", ""),
                "name": r.payload.get("name", ""),
                "roll_no": r.payload.get("roll_no", ""),
                "score": float(r.score),
                "distance": float(1 - r.score),
            })
        return matches

    def delete(self, uid: str):
        if self.client is None:
            return
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="uid", match=MatchValue(value=uid))]
            ),
        )

    def count(self):
        if self.client is None:
            return 0
        return self.client.count(collection_name=self.collection_name).count

    def clear(self):
        if self.client is None:
            return
        from qdrant_client.models import Filter
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(),
        )


vector_service = VectorService()
