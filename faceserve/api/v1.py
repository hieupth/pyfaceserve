import os
import base64
import pathlib
from PIL import Image
from io import BytesIO
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException, status, Request, File, UploadFile
from fastapi.staticfiles import StaticFiles
from faceserve.services.v1 import FaceServiceV1
from faceserve.models import HeadFace, GhostFaceNet
from faceserve.db.qdrant import QdrantFaceDatabase
from faceserve.schema.face_request import FaceRequest

"""
Load models and thresh.
"""
# Model
DETECTION = HeadFace(os.getenv("DETECTION_MODEL_PATH", default="weights/yolov7-hf-v1.onnx"))
RECOGNITION = GhostFaceNet(os.getenv("RECOGNITION_MODEL_PATH", default="weights/ghostnetv1.onnx"))
# Threshold
DETECTION_THRESH = os.getenv("DETECTION_THRESH", default=0.7)
RECOGNITION_THRESH = os.getenv("RECOGNITION_THRESH", default=0.4)
# Face db storage.
FACES = QdrantFaceDatabase(
    collection_name="faces_collection",
)
FACES_IMG_DIR = pathlib.Path(os.getenv("IMG_DIR", default="face_images"))
FACES_IMG_DIR.mkdir(exist_ok=True)

"""
Initialize Services
"""
service = FaceServiceV1(
    detection=DETECTION,
    detection_thresh=DETECTION_THRESH,
    recognition=RECOGNITION,
    recognition_thresh=RECOGNITION_THRESH,
    facedb=FACES,
)

"""
Router
"""
router = APIRouter(prefix="/v1")

@router.post("/register")
async def register(id: str, request: FaceRequest, groups_id: str = "default"):
    images = [base64.b64decode(x) for x in request.base64images]
    images = [Image.open(BytesIO(x)) for x in images]
    hash_imgs = service.register_face(images=images, id=id, group_id=groups_id, face_folder=FACES_IMG_DIR)
    return [f"/imgs/{groups_id}/{id}/{x}.jpg" for x in hash_imgs]


@router.post("/register/faces")
async def register_upload(files: list[UploadFile], id: str, group_id: str = "default"):
    images = [Image.open(BytesIO(await x.read())) for x in files]
    hash_imgs = service.register_face(images=images, id=id, group_id=group_id, face_folder=FACES_IMG_DIR)
    return [f"/imgs/{group_id}/{id}/{x}.jpg" for x in hash_imgs]


@router.get("/faces")
async def get_face_image(id: str|None = None, group_id: str|None = None):
    if not FACES.list_faces(person_id=id, group_id=group_id)[0]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No image found, database empty"
        )
    res = [x for x in FACES.list_faces(person_id=id, group_id=group_id)[0] if x is not None]
    output = []
    for x in res:
        res_group = x.payload["group_id"]
        res_person = x.payload["person_id"]
        res_hash = "".join(x.id.split("-"))
        output.append(f"/imgs/{res_group}/{res_person}/{res_hash}.jpg")
    return output

@router.delete("/delete")
async def delete_face(face_id: str|None = None, id: str|None = None, group_id: str|None = None):
    return FACES.delete_face(
        face_id=face_id, 
        person_id=id, 
        group_id=group_id
    )


@router.post("/check/face")
async def check_face_images(request: FaceRequest, id: str|None = None, group_id: str|None = None):
    images = [base64.b64decode(x) for x in request.base64images]
    images = [Image.open(BytesIO(x)) for x in images]
    return service.check_face(
        images=images, 
        thresh=RECOGNITION_THRESH, 
        person_id=id, 
        group_id=group_id
    )

@router.post("/check/faces")
async def check_faces(request: FaceRequest, id: str|None = None, group_id: str = 'default'):
    images = [base64.b64decode(x) for x in request.base64images]
    images = [Image.open(BytesIO(x)) for x in images]
    return service.check_faces(
        images=images, 
        thresh=RECOGNITION_THRESH,
        group_id=group_id
    )