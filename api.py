from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
from datetime import datetime
import json
import os
import pandas as pd

app = FastAPI()

DATA_FILE = "stores.json"
EXCEL_FILE = "stores_export.xlsx"


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

    # 🔥 신규 추가 — 등록일
    createdAt: str | None = None


class DeleteReq(BaseModel):
    name: str
    region: str


# =========================
# 파일 IO
# =========================
def load_data():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, encoding="utf-8-sig") as f:
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
# STORE LIST API (JSON)
# =========================
@app.get("/api/stores")
def get_stores():
    data = load_data()

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

    # 중복 방지 (name + region 기준)
    for s in data:
        if s["name"] == store.name and s["region"] == store.region:
            raise HTTPException(
                400,
                "이미 존재하는 매장입니다 (수정 기능을 사용하세요)"
            )

    obj = store.dict()

    # 🔥 최초 등록일 자동 기록
    if not obj.get("createdAt"):
        obj["createdAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data.append(normalize(obj))
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
        if s["name"] == store.name and s["region"] == store.region":

            obj = store.dict()

            # 🔥 기존 등록일 보존
            obj["createdAt"] = s.get("createdAt", "")

            data[i] = normalize(obj)
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


# =========================
# ADMIN — EXPORT EXCEL
# =========================
@app.get("/admin/export/excel")
def export_excel():

    data = load_data()

    if not data:
        raise HTTPException(404, "저장된 매장이 없습니다")

    # 정렬 기준 (최근 등록순)
    data = sorted(
        data,
        key=lambda x: x.get("createdAt", ""),
        reverse=True
    )

    df = pd.DataFrame(data)

    # 🔥 열 순서 정리
    cols = [
        "name", "region",
        "lat", "lng",
        "address",
        "kakaoOpenChat",
        "phoneNumber",
        "createdAt"
    ]

    df = df.reindex(columns=cols)

    df.rename(columns={
        "name": "매장명",
        "region": "지역",
        "lat": "위도",
        "lng": "경도",
        "address": "주소",
        "kakaoOpenChat": "카카오 오픈채팅",
        "phoneNumber": "전화번호",
        "createdAt": "등록일자"
    }, inplace=True)

    df.to_excel(EXCEL_FILE, index=False)

    return FileResponse(
        EXCEL_FILE,
        media_type="application/vnd.ms-excel",
        filename="store_list.xlsx"
    )
