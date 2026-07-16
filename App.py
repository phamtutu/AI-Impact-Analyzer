"""
API cho tính năng Break Task - wrap quanh break_task.py, gọi bằng Postman.

Chạy (1 lần cài đặt):
    pip install fastapi uvicorn langchain-google-genai pydantic

Chạy server:
    python app.py
    -> server chạy ở http://localhost:8000
    -> xem docs tự động, test thử ngay trên trình duyệt: http://localhost:8000/docs

Gọi bằng Postman:
    POST http://localhost:8000/break-task
    Header: Content-Type: application/json
    Body (raw JSON) - cách 1, dán nguyên code_map vào request:
    {
        "requirement": {
            "title": "Chống gửi trùng khi retry NPS",
            "requirement": "Cần retry gửi request NPS khi thất bại, đảm bảo không gửi trùng lặp.",
            "change_type": "Sửa tính năng có sẵn",
            "current_behavior": "Batch job retry gửi lại toàn bộ bản ghi failed mà không kiểm tra trạng thái.",
            "expected_behavior": "Kiểm tra MNP_STAT_CD trước khi gửi lại.",
            "business_rules": ["Không gửi lại nếu MNP_STAT_CD = SUCCESS", "Tối đa retry 3 lần"]
        },
        "code_map": { ... toàn bộ nội dung project-knowledge.json ... }
    }

    Body - cách 2, nếu file JSON quá to, không muốn dán vào Postman
    (server sẽ tự đọc file từ đường dẫn trên máy chạy server, có cache theo mtime):
    {
        "requirement": { ... như trên ... },
        "code_map_path": "project-knowledge.json"
    }
"""

import json
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import đúng tên module là break_task (snake_case) - khớp với tên file break_task.py.
# Nếu file thật của bạn tên là breakTask.py, đổi lại thành "from breakTask import ..."
# hoặc đổi tên file thành break_task.py cho đúng convention Python (khuyến nghị cách 2).
from breakTask import break_task, BreakdownResult, RequirementInput, load_code_map_cached, build_index


app = FastAPI(
    title="Source Code Task Breakdown API",
    description="Nhận requirement (structured) + code map (JSON từ analyzer.py) -> trả về impact analysis + task breakdown",
)


class BreakTaskRequest(BaseModel):
    requirement: RequirementInput
    code_map: Optional[Dict[str, Any]] = None
    code_map_path: Optional[str] = None


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Break Task API đang chạy"}


@app.post("/break-task", response_model=BreakdownResult)
def api_break_task(req: BreakTaskRequest):
    index = None

    if req.code_map is not None:
        code_map = req.code_map
        index = build_index(code_map)
    elif req.code_map_path:
        try:
            code_map, index = load_code_map_cached(req.code_map_path)
        except FileNotFoundError:
            raise HTTPException(
                status_code=400,
                detail=f"Không tìm thấy file: {req.code_map_path} (đường dẫn tính từ nơi chạy 'python app.py')",
            )
        except json.JSONDecodeError as ex:
            raise HTTPException(status_code=400, detail=f"File JSON không hợp lệ: {ex}")
    else:
        raise HTTPException(
            status_code=400,
            detail="Cần truyền 'code_map' (dán trực tiếp) hoặc 'code_map_path' (đường dẫn file trên server)",
        )

    try:
        result = break_task(req.requirement, code_map, index=index)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi AI phân tích: {ex}")

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)