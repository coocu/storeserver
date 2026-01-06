from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import os
import pandas as pd

app = FastAPI()

DATA_FILE = "stores.json"
EXCEL_FILE = "stores_export.xlsx"
PURGE_MONTHS = 6   # 완전 삭제 대기기간 (개월)


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
    createdAt: str | None = None
    deletedAt: str | None = None   # 휴지통 삭제일


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
# 6개월 지난 삭제 항목 자동 영구삭제
# =========================
def purge_expired(data: list):
    now = datetime.now()
    kept = []

    for s in data:
        deleted_at = s.get("deletedAt")

        # 삭제되지 않은 항목 → 유지
        if not deleted_at:
            kept.append(s)
            continue

        # 날짜 파싱 실패 시 유지
        try:
            dt = datetime.strptime(deleted_at, "%Y-%m-%d %H:%M:%S")
        except:
            kept.append(s)
            continue

        # 6개월 미경과 → 휴지통 유지
        if now - dt < timedelta(days=PURGE_MONTHS * 30):
            kept.append(s)

        # 6개월 경과 → 완전 삭제 (버림)

    save_data(kept)
    return kept


# =========================
# STORE LIST API (JSON)
# =========================
@app.get("/api/stores")
def get_stores():
    data = purge_expired(load_data())

    # 삭제 안 된 것만 내려보냄
    data = [
        normalize(s)
        for s in data
        if not s.get("deletedAt")
    ]

    text = json.dumps(data, ensure_ascii=False, indent=2)
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
            raise HTTPException(400, "이미 존재하는 매장입니다 (수정 기능 사용)")

    obj = store.dict()

    if not obj.get("createdAt"):
        obj["createdAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 신규 추가는 삭제상태 아님
    obj["deletedAt"] = None

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
        if s["name"] == store.name and s["region"] == store.region:

            obj = store.dict()

            obj["createdAt"] = s.get("createdAt", "")
            obj["deletedAt"] = s.get("deletedAt", None)

            data[i] = normalize(obj)
            updated = True
            break

    if not updated:
        raise HTTPException(404, "해당 매장을 찾을 수 없습니다")

    save_data(data)
    return {"status": "updated"}


# =========================
# ADMIN — SOFT DELETE (휴지통 이동)
# =========================
@app.post("/admin/delete")
def delete_store(req: DeleteReq):

    data = load_data()
    found = False

    for s in data:
        if s["name"] == req.name and s["region"] == req.region:

            if s.get("deletedAt"):
                raise HTTPException(400, "이미 휴지통 상태입니다")

            s["deletedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            found = True
            break

    if not found:
        raise HTTPException(404, "삭제 대상이 없습니다")

    save_data(data)
    return {"status": "soft-deleted"}


# =========================
# ADMIN — RESTORE (복구)
# =========================
@app.post("/admin/restore")
def restore_store(req: DeleteReq):

    data = load_data()
    restored = False

    for s in data:
        if s["name"] == req.name and s["region"] == req.region:

            if not s.get("deletedAt"):
                raise HTTPException(400, "삭제 상태가 아닙니다")

            s["deletedAt"] = None
            restored = True
            break

    if not restored:
        raise HTTPException(404, "복구 대상이 없습니다")

    save_data(data)
    return {"status": "restored"}


# =========================
# ADMIN — 휴지통 목록 API (신규)
# =========================
@app.get("/admin/trash")
def get_trash():

    data = purge_expired(load_data())

    trash = [
        s for s in data
        if s.get("deletedAt")
    ]

    # 삭제일 최신순 정렬
    trash = sorted(
        trash,
        key=lambda x: x.get("deletedAt", ""),
        reverse=True
    )

    return trash


# =========================
# ADMIN — EXPORT EXCEL (삭제되지 않은 데이터만)
# =========================
@app.get("/admin/export/excel")
def export_excel():

    data = purge_expired(load_data())

    data = [
        s for s in data
        if not s.get("deletedAt")
    ]

    if not data:
        raise HTTPException(404, "엑셀로 내보낼 매장이 없습니다")

    data = sorted(
        data,
        key=lambda x: x.get("createdAt", ""),
        reverse=True
    )

    df = pd.DataFrame(data)

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
