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
import os

from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import HTTPException
from typing import Optional
from math import ceil
from analyzer import analyze_project  

PROJECT_JSON = "project-knowledge.json"

# Import đúng tên module là break_task (snake_case) - khớp với tên file break_task.py.
# Nếu file thật của bạn tên là breakTask.py, đổi lại thành "from breakTask import ..."
# hoặc đổi tên file thành break_task.py cho đúng convention Python (khuyến nghị cách 2).
from breakTask import break_task, BreakdownResult, RequirementInput, load_code_map_cached, build_index


app = FastAPI(
    title="Source Code Task Breakdown API",
    description="Nhận requirement (structured) + code map (JSON từ analyzer.py) -> trả về impact analysis + task breakdown",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # khi dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeSourceRequest(BaseModel):
    source_path: str

class BreakTaskRequest(BaseModel):
    requirement: RequirementInput
    code_map: Optional[Dict[str, Any]] = None
    code_map_path: Optional[str] = None

def load_project():
    if not os.path.exists(PROJECT_JSON):
        raise HTTPException(
            status_code=404,
            detail="Chưa có project-knowledge.json. Hãy phân tích source code trước."
        )

    with open(PROJECT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/database")
def get_database():

    project = load_project()

    return [
        {
            "table": table["name"],
            "columns": [
                column["name"]
                for column in table["columns"]
            ]
        }
        for table in project["database_schema"]["tables"]
    ]

from typing import Optional

@app.get("/modules")
def get_modules(
    page: int = 1,
    size: int = 10,
    file_name: Optional[str] = None
):

    project = load_project()

    keyword = file_name.lower().strip() if file_name else None

    modules = []

    for module in project["modules"]:

        # LIKE %keyword%
        if keyword and keyword not in module["file_name"].lower():
            continue

        table_details = []

        for table in module.get("table_details", []):

            table_details.append({
                "table": table["name"],
                "columns": [
                    column["name"]
                    for column in table.get("columns", [])
                ]
            })

        modules.append({

            "file_name": module["file_name"],
            "file_path": module["file_path"],
            "package_name": module["package_name"],

            "module_name": module["module_name"],
            "module_type": module["module_type"],

            "summary": module.get("summary", ""),
            "source_class": module.get("source_class", ""),

            "methods": [
                {
                    "name": method["name"],
                    "endpoint": method.get("endpoint"),
                    "params": method.get("params", []),
                    "returns": method.get("returns")
                }
                for method in module.get("source_methods", [])
            ],

            "dependencies": module.get("dependencies", []),

            "tables": module.get("tables", []),

            "table_details": table_details,

            "related_files": [
                file.split("/")[-1]
                for file in module.get("related_files", [])
            ]
        })

    total = len(modules)

    start = (page - 1) * size
    end = start + size

    return {
        "page": page,
        "size": size,
        "total": total,
        "total_pages": ceil(total / size) if total else 0,
        "data": modules[start:end]
    }

@app.get("/project")
def get_project():

    project = load_project()

    return {
        "name": project["project"]["name"],
        "path": project["project"]["path"],
        "database": project["database"]["db_type"],
        "total_tables": len(project["database_schema"]["tables"]),
        "total_modules": len(project["modules"])
    }

@app.post("/analyze-source")
def analyze_source(req: AnalyzeSourceRequest):

    if not os.path.exists(req.source_path):
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy thư mục source code"
        )

    if not os.path.isdir(req.source_path):
        raise HTTPException(
            status_code=400,
            detail="source_path phải là một thư mục"
        )

    try:
        result = analyze_project(req.source_path)

        return {
            "status": "success",
            "message": "Phân tích source code thành công",
            "result": result
        }

    except Exception as ex:
        raise HTTPException(
            status_code=500,
            detail=str(ex)
        )

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