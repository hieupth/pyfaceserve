import os
from typing import Optional, Any, List, Tuple
from qdrant_client.http import models
from qdrant_client import QdrantClient

from .interface import InterfaceDatabase


class QdrantFaceDatabase(InterfaceDatabase):
    def __init__(
        self,
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=os.getenv("QDRANT_PORT", 6333),
        url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._client = self.connect_client(host, port, url, api_key)

    def connect_client(self, host, port, url, api_key):
        if url is not None and api_key is not None:
            # cloud instance
            return QdrantClient(url=url, api_key=api_key)
        elif url is not None:
            # local instance with differ url
            return QdrantClient(url=url)
        else:
            return QdrantClient(host=host, port=port)
        
    def create_colection(self, collection_name, dimension=512, distance='cosine') -> None:
        # resolve distance
        if distance == 'euclidean':
            distance = models.Distance.EUCLID
        elif distance == 'dot':
            distance = models.Distance.DOT
        elif distance == 'manhattan':
            distance = models.Distance.MANHATTAN
        else: 
            distance = models.Distance.COSINE

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=dimension, distance=distance
            ),
        )

    def insert_person(
        self, 
        collection_name,
        data_face: List[Tuple[str, List[Any]]], 
        student_id: str, 
        group_id: str, 
    ):
        '''Insert list of faces of a person to collection'''
        self._client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=hash_id, 
                    vector=face_emb,
                    payload={
                        'student_id': student_id,
                        'group_id': group_id,
                    }
                ) for hash_id, face_emb in data_face 
            ],
        )

    def list_person(self):
        ids = self._client.get_collections().collections
        ids = [i.name for i in ids]
        return ids

    def delete_person(self, person_id):
        self._client.delete_collection(person_id)

    def insert_face(self, person_id, face_id, face_emb):
        self._client.upsert(
            collection_name=person_id,
            points=[models.PointStruct(id=face_id, vector=face_emb)],
        )

    def list_face(self, person_id):
        return self._client.scroll(collection_name=person_id, limit=1000)

    def delete_face(self, person_id, face_id):
        self._client.delete_vectors(
            collection_name=person_id, points_selector=models.PointIdsList([face_id])
        )

    def check_face(self, person_id, face_emb, thresh):
        res = self._client.search(
            collection_name=person_id, query_vector=face_emb, limit=1
        )
        if len(res) > 0:
            for r in res:
                if r.score > thresh:
                    return True
        return False
