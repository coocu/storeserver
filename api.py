from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import json
import os

app = FastAPI()

DATA_FILE = "stores.json"


# =========================
# 모델 정의
# =========================
class Store(BaseModel):
    name: str
    region: str
    lat: str | None = ""
    lng: str | None = ""
    address: str | None = ""
    kakaoOpenChat: str | None = ""
    phoneNumber: str | None = ""


class DeleteReq(BaseModel):
    name: str
    region: str


# =========================
# 파일 IO
# =========================
def load_data():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# 값 정규화 (None → "")
# =========================
def normalize(store: dict):
    for k, v in store.items():
        if v is None:
            store[k] = ""
    return store


# =========================
# STORE LIST API
# (앱 JSON 파서와 100% 호환)
# =========================
@app.get("/api/stores")
def get_stores():
    data = load_data()

    # None 값이 있으면 optString() 이 "" 로 받도록 통일
    data = [normalize(s) for s in data]

    text = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )

    body = text.encode("utf-8")

    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Length": str(len(body)),
            "Cache-Control": "no-cache"
        }
    )


# =========================
# ADMIN — ADD
# =========================
@app.post("/admin/add")
def add_store(store: Store):

    data = load_data()

    for s in data:
        if s["name"] == store.name and s["region"] == store.region:
            raise HTTPException(
                400,
                "이미 존재하는 매장입니다 (수정 기능을 사용하세요)"
            )

    data.append(normalize(store.dict()))
    save_data(data)

    return {"status": "added", "count": len(data)}


# =========================
# ADMIN — UPDATE
# =========================
@app.put("/admin/update")
def update_store(store: Store):

    data = load_data()
    updated = False

    for i, s in enumerate(data):
        if s["name"] == store.name and s["region"] == store.region:
            data[i] = normalize(store.dict())
            updated = True
            break

    if not updated:
            raise HTTPException(404, "해당 매장을 찾을 수 없습니다")

    save_data(data)

    return {"status": "updated"}


# =========================
# ADMIN — DELETE
# =========================
@app.post("/admin/delete")
def delete_store(req: DeleteReq):

    data = load_data()

    new_data = [
        s for s in data
        if not (s["name"] == req.name and s["region"] == req.region)
    ]

    if len(new_data) == len(data):
        raise HTTPException(404, "삭제 대상이 없습니다")

    save_data(new_data)

    return {"status": "deleted", "count": len(new_data)}
