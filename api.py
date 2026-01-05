from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import os

app = FastAPI()

DATA_FILE = "stores.json"


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


def load_data():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.get("/api/stores")
def get_stores():
    return load_data()


@app.post("/admin/add")
def add_store(store: Store):

    data = load_data()

    for s in data:
        if s["name"] == store.name and s["region"] == store.region:
            raise HTTPException(400, "이미 존재하는 매장입니다 (수정 기능을 사용하세요)")

    data.append(store.dict())
    save_data(data)

    return {"status": "added", "count": len(data)}


@app.put("/admin/update")
def update_store(store: Store):

    data = load_data()
    updated = False

    for i, s in enumerate(data):
        if s["name"] == store.name and s["region"] == store.region:
            data[i] = store.dict()
            updated = True
            break

    if not updated:
        raise HTTPException(404, "해당 매장을 찾을 수 없습니다")

    save_data(data)

    return {"status": "updated"}


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
