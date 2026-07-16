"""
BREAK TASK - dùng Gemini 3.5 Flash (LangChain) để phân tích impact + chia task.
(Chưa tính effort - effort sẽ là bước riêng sau khi task breakdown đã ổn.)

Input requirement giờ là STRUCTURED (không còn 1 field text tự do):
    title, requirement, change_type, current_behavior, expected_behavior, business_rules

Code map giờ theo schema MỚI (giàu hơn): có database_schema (bảng + cột chi tiết),
method_key có sẵn, affected_columns theo từng method.

CHẠY TRỰC TIẾP: sửa phần CONFIG bên dưới rồi chạy:
    python break_task.py

Cài đặt trước (1 lần):
    pip install langchain-google-genai pydantic
"""

import json
import os
import re
import math
import time

from collections import Counter
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage


# ============================================================
# CONFIG
# ============================================================
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CODE_MAP_PATH = os.getenv(
    "CODE_MAP_PATH",
    "project-knowledge.json",
)

if not GOOGLE_API_KEY:
    raise RuntimeError(
        "Chưa cấu hình GOOGLE_API_KEY trong file .env"
    )

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Input requirement giờ có cấu trúc, không còn 1 field text tự do.
REQUIREMENT_INPUT = {
    "title": "Chống gửi trùng khi retry NPS",
    "requirement": "Cần retry gửi request NPS khi thất bại, đảm bảo không gửi trùng lặp.",
    "change_type": "Sửa tính năng có sẵn",
    "current_behavior": "Batch job retry gửi lại toàn bộ bản ghi failed mà không kiểm tra đã gửi thành công trước đó hay chưa.",
    "expected_behavior": "Trước khi gửi lại, phải kiểm tra trạng thái MNP_STAT_CD - chỉ retry nếu chưa ở trạng thái thành công.",
    "business_rules": [
        "Không được gửi lại nếu MNP_STAT_CD đã là 'SUCCESS'",
        "Mỗi bản ghi tối đa retry 3 lần (RETRY_COUNT)",
    ],
}

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

CHANGE_TYPES = ["Tính năng mới", "Sửa tính năng có sẵn", "Sửa lỗi (bugfix)", "Gỡ bỏ tính năng", "Khác"]


class RequirementInput(BaseModel):
    title: str = Field(description="Tiêu đề ngắn gọn")
    requirement: str = Field(description="Mô tả yêu cầu nghiệp vụ")
    change_type: str = Field(default="Khác", description=f"Một trong: {CHANGE_TYPES}")
    current_behavior: str = Field(default="", description="Hành vi hiện tại (nếu là sửa tính năng có sẵn)")
    expected_behavior: str = Field(default="", description="Hành vi mong muốn sau khi thay đổi")
    business_rules: List[str] = Field(default_factory=list, description="Các business rule cụ thể cần tuân thủ")


def count_prompt_tokens(llm, system_prompt, user_prompt):
    try:
        text = system_prompt + "\n\n" + user_prompt

        response = llm.client.models.count_tokens(
            model="gemini-3.5-flash",
            contents=text,
        )

        return response.total_tokens

    except Exception as e:
        print(f"[WARN] Không đếm được token: {e}")
        return None

def requirement_to_search_text(req: RequirementInput) -> str:
    """Gộp toàn bộ field thành 1 đoạn text để dùng cho bước rule_based_filter (tokenize/matching)."""
    parts = [req.title, req.requirement, req.current_behavior, req.expected_behavior]
    parts.extend(req.business_rules)
    return "\n".join(p for p in parts if p)


def requirement_to_prompt_text(req: RequirementInput) -> str:
    """Format có cấu trúc rõ ràng để đưa vào prompt cho AI - KHÔNG gộp chung 1 blob nữa,
    để AI phân biệt được đâu là hành vi hiện tại/mong muốn/business rule."""
    rules_text = "\n".join(f"  - {r}" for r in req.business_rules) if req.business_rules else "  (không có)"
    return f"""Tiêu đề: {req.title}
Loại thay đổi: {req.change_type}

Mô tả yêu cầu:
{req.requirement}

Hành vi hiện tại:
{req.current_behavior or "(không có - có thể là tính năng hoàn toàn mới)"}

Hành vi mong muốn sau khi thay đổi:
{req.expected_behavior or "(chưa nêu rõ)"}

Business rules cần tuân thủ:
{rules_text}
"""


# ============================================================
# BƯỚC 1: LỌC THÔ - INDEX + SCORING + MATCH TÊN BẢNG TRỰC TIẾP
# ============================================================

STOPWORDS = {
    "cần", "cho", "khi", "để", "và", "cùng", "đảm", "bảo", "không", "được",
    "này", "đó", "các", "những", "một", "có", "là", "của", "với", "theo",
    "sau", "trước", "hoặc", "nếu", "thì", "sẽ", "đã", "đang", "phải", "nên",
}


def _is_hangul_token(token):
    return any("\uAC00" <= ch <= "\uD7A3" for ch in token)


def _tokenize(text):
    if not text:
        return set()

    # QUAN TRỌNG: bản cũ dùng whitelist [A-Za-z0-9가-힣...] để tách từ - ký tự có dấu tiếng Việt
    # (ả, ệ, ạ, ố...) KHÔNG nằm trong whitelist này nên bị coi là dấu phân cách, làm vỡ nát từ
    # tiếng Việt (vd "Quản lý" -> mất hoàn toàn, "trùng lặp" -> chỉ còn rác). Dùng \w (Unicode-aware
    # trong Python 3, tự nhận diện chữ cái có dấu của mọi ngôn ngữ) để tách đúng theo khoảng trắng/
    # dấu câu thay vì whitelist ký tự.
    words = re.split(r"[^\w]+", text, flags=re.UNICODE)

    tokens = []
    for w in words:
        if not w:
            continue

        # Chỉ tách kiểu camelCase (npsSendRetryBatch -> nps, send, retry, batch) cho từ THUẦN ASCII
        # (định danh code Java). Từ có dấu tiếng Việt/tiếng Hàn giữ nguyên cả cụm - cố tách camelCase
        # trên ký tự có dấu sẽ làm vỡ từ y hệt lỗi ở whitelist cũ.
        if w.isascii():
            camel_parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", w)
            tokens.extend(camel_parts if camel_parts else [w])
        else:
            tokens.append(w)

    result = set()
    for t in tokens:
        t_lower = t.lower()
        if t_lower in STOPWORDS:
            continue
        # Từ tiếng Hàn thường chỉ 2 âm tiết đã mang nghĩa (기업=doanh nghiệp, 유선=hữu tuyến,
        # 배치=batch...) - ngưỡng len>2 dùng cho Latin sẽ loại sạch từ Hàn ngắn này, nên nới
        # riêng xuống len>=2 cho token có chứa Hangul.
        min_len = 2 if _is_hangul_token(t) else 3
        if len(t) >= min_len:
            result.add(t_lower)

    return result


def build_index(code_map):
    name_to_module = {}
    module_tokens = {}
    method_tokens = {}
    df = Counter()

    table_to_modules = {}
    column_to_modules = {}

    database_tables = (
        code_map.get("database_schema", {})
        .get("tables", [])
    )

    all_table_names = []
    all_column_names = []

    for table in database_tables:
        table_name = table.get("name", "")
        if table_name:
            all_table_names.append(table_name)

        for column in table.get("columns", []):
            column_name = column.get("name", "")
            if column_name:
                all_column_names.append(column_name)

    for module in code_map.get("modules", []):
        module_name = module["module_name"]
        name_to_module[module_name] = module

        current_module_tokens = set()

        current_module_tokens |= _tokenize(module_name)
        current_module_tokens |= _tokenize(module.get("summary", ""))
        current_module_tokens |= _tokenize(module.get("module_type", ""))

        for table_name in module.get("tables", []):
            current_module_tokens |= _tokenize(table_name)
            table_to_modules.setdefault(
                table_name.upper(),
                set()
            ).add(module_name)

        for integration in module.get("external_integrations", []):
            if isinstance(integration, str):
                current_module_tokens |= _tokenize(integration)
            elif isinstance(integration, dict):
                current_module_tokens |= _tokenize(
                    json.dumps(integration, ensure_ascii=False)
                )

        for method in module.get("source_methods", []):
            method_key = (
                method.get("method_key")
                or f"{module_name}.{method.get('name', '')}"
            )

            current_method_tokens = set()

            current_method_tokens |= _tokenize(method.get("name", ""))
            current_method_tokens |= _tokenize(method_key)
            current_method_tokens |= _tokenize(method.get("endpoint", ""))

            for called_method in method.get("calls_to_internal", []):
                current_method_tokens |= _tokenize(called_method)

            for table_name in method.get("affected_tables", []):
                current_method_tokens |= _tokenize(table_name)

                table_to_modules.setdefault(
                    table_name.upper(),
                    set()
                ).add(module_name)

            for table_name, columns in method.get(
                "affected_columns",
                {}
            ).items():
                current_method_tokens |= _tokenize(table_name)

                table_to_modules.setdefault(
                    table_name.upper(),
                    set()
                ).add(module_name)

                for column_name in columns:
                    current_method_tokens |= _tokenize(column_name)

                    column_to_modules.setdefault(
                        column_name.upper(),
                        set()
                    ).add(module_name)

            method_tokens[method_key] = current_method_tokens
            current_module_tokens |= current_method_tokens

        module_tokens[module_name] = current_module_tokens

        for token in current_module_tokens:
            df[token] += 1

    return {
        "name_to_module": name_to_module,
        "module_tokens": module_tokens,
        "method_tokens": method_tokens,
        "df": df,
        "total_modules": len(name_to_module),
        "table_to_modules": table_to_modules,
        "column_to_modules": column_to_modules,
        "all_table_names": all_table_names,
        "all_column_names": all_column_names,
    }


_INDEX_CACHE = {}


def load_code_map_cached(path):
    mtime = os.path.getmtime(path)
    cached = _INDEX_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1], cached[2]
    code_map = json.load(open(path, encoding="utf-8"))
    index = build_index(code_map)
    _INDEX_CACHE[path] = (mtime, code_map, index)
    return code_map, index


def rule_based_filter(requirement_text, code_map, index=None, max_hops=1,
                       max_modules=5, min_relative_score=0.15):
    """
    So khớp requirement với module dùng trọng số kiểu IDF (Inverse Document Frequency):
    từ khoá càng xuất hiện ở nhiều module thì trọng số càng THẤP (không bị LOẠI HẲN như bản cũ),
    từ khoá càng hiếm/đặc trưng thì trọng số càng CAO.

    Lý do đổi từ cắt ngưỡng nhị phân (generic_threshold cũ) sang IDF: nếu requirement chỉ có
    đúng 1 từ khoá có ý nghĩa và từ đó lại là tên 1 entity trung tâm (vd "user" xuất hiện ở
    UserService/UserController/UserRepository/...), cắt nhị phân sẽ loại sạch từ đó -> 0 kết quả.
    IDF vẫn tính nhưng trọng số thấp hơn -> vẫn ra kết quả hợp lý thay vì rơi về rỗng.

    min_relative_score: 1 module phải đạt >= 15% của điểm tối đa lý thuyết (tổng trọng số toàn
    bộ token trong requirement) mới được chọn. Luôn giữ tối thiểu 1 module (module có score cao
    nhất) nếu có bất kỳ match nào, để tránh rơi về rỗng một cách giả tạo.
    """
    idx = index or build_index(code_map)
    total = idx["total_modules"] or 1

    req_tokens = _tokenize(requirement_text)
    matched_names = set()

    if req_tokens:
        def idf(token):
            df = idx["df"].get(token, 0)
            return math.log((total + 1) / (df + 1)) + 1

        weights = {t: idf(t) for t in req_tokens}
        max_possible_score = sum(weights.values()) or 1

        scores = {}
        for name, tokens in idx["doc_tokens"].items():
            matched_tokens = tokens & req_tokens
            if matched_tokens:
                scores[name] = sum(weights[t] for t in matched_tokens)

        if scores:
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            threshold = max_possible_score * min_relative_score
            matched_names = {name for name, score in ranked if score >= threshold}

            # Không để rơi về rỗng một cách giả tạo nếu CÓ match nhưng không ai vượt threshold
            if not matched_names:
                matched_names = {ranked[0][0]}

            matched_names = set(name for name, _ in ranked[:max_modules]) & matched_names \
                if len(matched_names) > max_modules else matched_names

    # Match trực tiếp tên bảng - tín hiệu MẠNH và chính xác hơn keyword thường, vì requirement
    # nhắc thẳng tên bảng (vd "MNP_STAT_CD", "TB_CORP_WIRED_MNP") là chủ đích rõ ràng của người viết.
    requirement_upper = requirement_text.upper()
    for table_name in idx["all_table_names"]:
        if table_name in requirement_upper:
            matched_names |= idx["table_to_modules"].get(table_name, set())

    name_to_module = idx["name_to_module"]
    frontier = set(matched_names)
    for _ in range(max_hops):
        next_frontier = set()
        for name in frontier:
            module = name_to_module.get(name)
            if not module:
                continue
            for dep in module.get("dependencies", []):
                if dep in name_to_module:
                    next_frontier.add(dep)
        matched_names |= next_frontier
        frontier = next_frontier

    return [name_to_module[n] for n in matched_names if n in name_to_module]


def get_relevant_schema(code_map, filtered_modules):
    """Chỉ lấy phần database_schema của các bảng THẬT SỰ liên quan tới module đã lọc,
    không đưa nguyên 10 bảng cho AI (tốn token, dư thừa)."""
    relevant_tables = set()
    for m in filtered_modules:
        relevant_tables.update(m.get("tables", []))

    all_tables = code_map.get("database_schema", {}).get("tables", [])
    return [
        {"name": t["name"], "columns": [c["name"] for c in t.get("columns", [])]}
        for t in all_tables if t["name"] in relevant_tables
    ]


# ============================================================
# BƯỚC 2: SCHEMA OUTPUT + PROMPT + GỌI GEMINI
# ============================================================

class ImpactedModule(BaseModel):
    module: str = Field(description="Tên module/class bị ảnh hưởng")
    impact_level: str = Field(description="'direct' hoặc 'indirect'")
    reason: str = Field(description="Lý do ngắn gọn vì sao module này bị ảnh hưởng")


PROCESS_TYPES = ["Online", "Batch", "I/F", "DB", "Report", "BW", "DW", "PV", "RPA", "모바일", "기타"]

FUNCTION_TYPES = ["입력/Nhập", "수정/Edit", "삭제/Xóa", "조회/Query"]

class UnitProcess(BaseModel):
    no: int = Field(default=0, description="Số thứ tự - để 0, code sẽ tự đánh số lại")
    level1: str = Field(description="LEVEL1 업무/시스템 명 - tên hệ thống/nghiệp vụ cấp 1")
    level2: str = Field(description="LEVEL2 주업무 명 - tên nghiệp vụ chính")
    level3: str = Field(description="LEVEL3 화면 혹은 상세업무명 - tên màn hình/nghiệp vụ chi tiết, tiếng Việt")
    level4: str = Field(description="LEVEL4 단위프로세스명 - tên đơn vị xử lý, tiếng Việt, ngắn gọn")
    description: str = Field(
        description="단위프로세스 상세구현 설명 - mô tả chi tiết, PHẢI liệt kê rõ tên bảng và cột thật "
                    "lấy từ database_schema/affected_columns được cung cấp (vd: '- TB_CORP_WIRED_MNP (MNP_STAT_CD, RETRY_COUNT)')"
    )
    dev_type: str = Field(description="개발유형 - loại hình phát triển kỹ thuật")
    process_type: str = Field(description=f"처리유형 - PHẢI chọn đúng 1 trong: {PROCESS_TYPES}")
    function_type: str = Field(description=f"기능유형 - PHẢI chọn đúng 1 trong: {FUNCTION_TYPES}")
    module: str = Field(default="", description="Module/class kỹ thuật liên quan - để truy vết nội bộ")
    related_methods: List[str] = Field(
        default_factory=list,
        description="Danh sách method_key liên quan (đúng giá trị field 'method_key' trong Code Map, "
                    "vd 'CorpWiredMnpBatchJob.npsSendRetryBatch'), để truy vết nội bộ"
    )


class BreakdownResult(BaseModel):
    impacted_modules: List[ImpactedModule]
    unit_processes: List[UnitProcess]
    mode: str = Field(default="impact_based", description="'impact_based' hoặc 'requirement_based'")


LANGUAGE_RULE = """
QUY TẮC NGÔN NGỮ BẮT BUỘC:
- Toàn bộ text mô tả (level1, level2, level3, level4, description, dev_type) dùng tiếng Việt.
- Riêng process_type và function_type PHẢI giữ NGUYÊN VĂN đúng 1 giá trị trong danh sách enum
  được cung cấp (không dịch, không tự bịa thêm giá trị khác).
- Không được sinh tiếng Hàn ở các trường mô tả tự do.
"""

SYSTEM_PROMPT = f"""{LANGUAGE_RULE}

Bạn là trợ lý phân tích impact và định nghĩa Unit Process cho hệ thống phần mềm.

Bạn chỉ được sử dụng:
- Requirement được cung cấp.
- Module trong code_context.
- method_key trong source_methods.
- Bảng và cột trong database_context hoặc affected_columns.

Không được tự bịa module, method, bảng hoặc cột.

Không ước lượng effort hoặc số giờ.

QUY TẮC BREAKDOWN:

1. Mỗi unit process chỉ thể hiện đúng một hành vi cụ thể.

2. Nếu một luồng có nhiều hành vi độc lập, phải tách thành nhiều unit process.

Ví dụ luồng retry NPS phải có thể tách thành:

- Truy vấn bản ghi NPS đủ điều kiện retry.
- Kiểm tra MNP_STAT_CD trước khi gửi.
- Kiểm tra giới hạn RETRY_COUNT.
- Gửi lại request NPS.
- Cập nhật trạng thái sau khi gửi thành công.
- Tăng RETRY_COUNT sau khi gửi thất bại.

3. Không được gộp thành một unit process chung chung như:
- Xử lý retry NPS.
- Cập nhật dữ liệu.
- Thực hiện nghiệp vụ.
- Xử lý báo cáo.
- Quản lý thông tin.

4. level4 phải là tên hành vi cụ thể nhất, thể hiện:
- Hành động.
- Đối tượng xử lý.
- Điều kiện quan trọng nếu có.

Ví dụ level4 tốt:
- Truy vấn bản ghi NPS có MNP_STAT_CD khác SUCCESS.
- Loại bỏ bản ghi đã đạt giới hạn RETRY_COUNT.
- Cập nhật MNP_STAT_CD sau khi gửi thành công.
- Tăng RETRY_COUNT sau khi gửi thất bại.

5. Quy tắc tác động DB:

- Mỗi thao tác SELECT, INSERT, UPDATE hoặc DELETE độc lập nên được biểu diễn
  thành một database_impact.
- table và columns phải tồn tại trong database_context.
- operation chỉ được nhận SELECT, INSERT, UPDATE hoặc DELETE.
- condition phải mô tả điều kiện bằng tên cột thật nếu dữ liệu đầu vào có cung cấp.
- Không tự suy đoán câu SQL nếu Code Map không có đủ dữ liệu.
- Nếu không xác định được bảng/cột thì database_impacts=[].
- Tuyệt đối không tự bịa bảng hoặc cột để làm output đầy đủ.

6. related_methods chỉ được dùng đúng method_key trong code_context.

7. Phân loại impact:
- direct: module trực tiếp phải sửa.
- indirect: module không nhất thiết sửa nhưng bị ảnh hưởng bởi luồng gọi hoặc dữ liệu.

8. Mỗi business rule phải được thể hiện trong ít nhất một unit process.

9. Với change_type là tính năng mới:
- Breakdown theo hành vi cần phát triển.
- Không được tự bịa module, method hoặc bảng chưa tồn tại.
- Thành phần chưa xác định phải để module="", related_methods=[],
  database_impacts=[].

10. Với change_type là sửa tính năng có sẵn:
- Tập trung vào sự khác biệt giữa current_behavior và expected_behavior.
- Chỉ sinh unit process thực sự cần thay đổi.

Cấu trúc mỗi unit process:

- level1: hệ thống hoặc nhóm nghiệp vụ.
- level2: nghiệp vụ chính.
- level3: chức năng hoặc luồng xử lý.
- level4: hành vi cụ thể nhất.
- description: nội dung triển khai chi tiết.
- module: module/class liên quan.
- related_methods: method_key liên quan.
- database_impacts: bảng, thao tác, cột và điều kiện dữ liệu.
- process_type: phải thuộc {PROCESS_TYPES}.
- function_type: phải thuộc {FUNCTION_TYPES}.

Nhiệm vụ:

1. Xác định module bị ảnh hưởng trực tiếp và gián tiếp.
2. Tách requirement thành các unit process cụ thể nhất có thể.
3. Gắn unit process với module, method và DB nếu dữ liệu có thể chứng minh.
4. Không tạo task chung chung như phân tích, coding, review hoặc unit test.
"""


def build_user_prompt(
    req: RequirementInput,
    code_map,
    selected_modules,
    max_methods_per_module=5,
):
    requirement_text = requirement_to_search_text(req)

    compact_modules = []
    selected_table_columns = {}

    for selected in selected_modules:
        module = selected["module"]

        relevant_methods = select_relevant_methods(
            module=module,
            requirement_text=requirement_text,
            max_methods=max_methods_per_module,
        )

        compact_methods = []

        for method_result in relevant_methods:
            method = method_result["method"]

            affected_columns = method.get(
                "affected_columns",
                {}
            )

            for table_name, columns in affected_columns.items():
                selected_table_columns.setdefault(
                    table_name,
                    set(),
                ).update(columns)

            compact_method = {
                "method_key": (
                    method.get("method_key")
                    or f"{module['module_name']}.{method.get('name', '')}"
                ),
                "name": method.get("name", ""),
            }

            if method.get("endpoint"):
                compact_method["endpoint"] = method["endpoint"]

            if method.get("affected_tables"):
                compact_method["affected_tables"] = (
                    method["affected_tables"]
                )

            if affected_columns:
                compact_method["affected_columns"] = affected_columns

            compact_methods.append(compact_method)

        compact_module = {
            "module_name": module["module_name"],
            "module_type": module.get("module_type", ""),
            "summary": module.get("summary", ""),
            "match_score": selected["score"],
            "match_reasons": selected["match_reasons"],
            "source_methods": compact_methods,
        }

        compact_modules.append(compact_module)

    # Chỉ gửi đúng table/column đã xuất hiện trong method được chọn
    compact_schema = [
        {
            "name": table_name,
            "columns": sorted(columns),
        }
        for table_name, columns in selected_table_columns.items()
    ]

    prompt_data = {
        "requirement": req.model_dump(),
        "code_context": compact_modules,
        "database_context": compact_schema,
    }

    # Không indent để giảm token
    return json.dumps(
        prompt_data,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        temperature=0.2,
        timeout=30,
        thinking_level="low",
    )
    
def select_relevant_methods(
    module,
    requirement_text,
    max_methods=5,
):
    req_tokens = _tokenize(requirement_text)
    requirement_upper = requirement_text.upper()

    scored_methods = []

    for method in module.get("source_methods", []):
        method_key = (
            method.get("method_key")
            or f"{module['module_name']}.{method.get('name', '')}"
        )

        method_tokens = set()
        method_tokens |= _tokenize(method.get("name", ""))
        method_tokens |= _tokenize(method_key)
        method_tokens |= _tokenize(method.get("endpoint", ""))

        for table_name in method.get("affected_tables", []):
            method_tokens |= _tokenize(table_name)

        for table_name, columns in method.get(
            "affected_columns",
            {}
        ).items():
            method_tokens |= _tokenize(table_name)

            for column_name in columns:
                method_tokens |= _tokenize(column_name)

        matched_tokens = req_tokens & method_tokens
        score = len(matched_tokens)

        exact_tables = []
        exact_columns = []

        affected_tables = set(method.get("affected_tables", []))
        affected_tables.update(
            method.get("affected_columns", {}).keys()
        )

        for table_name in affected_tables:
            if table_name.upper() in requirement_upper:
                exact_tables.append(table_name)
                score += 10

        for table_name, columns in method.get(
            "affected_columns",
            {}
        ).items():
            for column_name in columns:
                if column_name.upper() in requirement_upper:
                    exact_columns.append(
                        f"{table_name}.{column_name}"
                    )
                    score += 8

        if score > 0:
            scored_methods.append({
                "score": score,
                "method": method,
                "matched_tokens": sorted(matched_tokens),
                "exact_tables": exact_tables,
                "exact_columns": exact_columns,
            })

    scored_methods.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return scored_methods[:max_methods]

def score_modules(
    requirement_text,
    code_map,
    index=None,
    max_modules=5,
    min_relative_score=0.12,
):
    idx = index or build_index(code_map)

    total_modules = idx["total_modules"] or 1
    req_tokens = _tokenize(requirement_text)
    requirement_upper = requirement_text.upper()

    def idf(token):
        document_frequency = idx["df"].get(token, 0)
        return math.log(
            (total_modules + 1) / (document_frequency + 1)
        ) + 1

    token_weights = {
        token: idf(token)
        for token in req_tokens
    }

    scores = Counter()
    reasons = {}

    for module_name, tokens in idx["module_tokens"].items():
        matched_tokens = tokens & req_tokens

        if not matched_tokens:
            continue

        score = sum(
            token_weights[token]
            for token in matched_tokens
        )

        scores[module_name] += score
        reasons.setdefault(module_name, []).append(
            f"keyword={sorted(matched_tokens)}"
        )

    # Exact match tên bảng: tín hiệu rất mạnh
    for table_name in idx["all_table_names"]:
        if table_name.upper() in requirement_upper:
            for module_name in idx["table_to_modules"].get(
                table_name.upper(),
                set(),
            ):
                scores[module_name] += 10
                reasons.setdefault(module_name, []).append(
                    f"table={table_name}"
                )

    # Exact match tên cột: tín hiệu mạnh
    for column_name in idx["all_column_names"]:
        if column_name.upper() in requirement_upper:
            for module_name in idx["column_to_modules"].get(
                column_name.upper(),
                set(),
            ):
                scores[module_name] += 8
                reasons.setdefault(module_name, []).append(
                    f"column={column_name}"
                )

    if not scores:
        return []

    ranked = scores.most_common()

    best_score = ranked[0][1]
    threshold = best_score * min_relative_score

    results = []

    for module_name, score in ranked:
        if score < threshold:
            continue

        results.append({
            "module": idx["name_to_module"][module_name],
            "score": round(score, 4),
            "match_reasons": reasons.get(module_name, []),
            "relation": "direct",
        })

        if len(results) >= max_modules:
            break

    return results

def break_task(req: RequirementInput, code_map, llm=None, index=None):
    if isinstance(req, dict):
        req = RequirementInput(**req)

    search_text = requirement_to_search_text(req)

    t0 = time.time()

    selected_modules = score_modules(
        requirement_text=search_text,
        code_map=code_map,
        index=index,
        max_modules=5,
        min_relative_score=0.20,
    )

    t1 = time.time()

    print(
        f"[TIME] retrieval: {t1 - t0:.2f}s"
        f" -> {len(selected_modules)} module: "
        f"{[item['module']['module_name'] for item in selected_modules]}"
    )

    llm = llm or build_llm()
    structured_llm = llm.with_structured_output(BreakdownResult)

    if not selected_modules:
        print(
            "[INFO] Không tìm thấy module liên quan "
            "-> Requirement Based Mode"
        )

        generic_prompt = f"""
                            {LANGUAGE_RULE}

                            YÊU CẦU:
                            {requirement_to_prompt_text(req)}

                            Không tìm thấy code hiện tại liên quan trong Code Map.

                            Yêu cầu output:
                            - impacted_modules=[]
                            - mode="requirement_based"
                            - Chia theo hành vi nghiệp vụ cần phát triển.
                            - Không sinh task chung chung như phân tích, coding, unit test.
                            - Không tự bịa module, method, bảng hoặc cột.
                            - module=""
                            - related_methods=[]
                            - Mỗi business rule phải xuất hiện trong ít nhất một unit process.
                            """

        t2 = time.time()

        result = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=generic_prompt),
        ])

        t3 = time.time()

        print(
            f"[TIME] Gemini requirement_based: "
            f"{t3 - t2:.2f}s"
        )

        result_dict = result.model_dump()
        result_dict["mode"] = "requirement_based"
        
        user_prompt = build_user_prompt(
        req=req,
        code_map=code_map,
        selected_modules=selected_modules,
        max_methods_per_module=5,
    )
        
        prompt_tokens = count_prompt_tokens(
                        llm,
                        SYSTEM_PROMPT,
                        user_prompt)

        if prompt_tokens:
            print(
                f"[INFO] Prompt tokens thực tế: "
                f"{prompt_tokens:,}"
            )

        for i, unit_process in enumerate(
            result_dict["unit_processes"],
            start=1,
        ):
            unit_process["no"] = i

        return result_dict

    user_prompt = build_user_prompt(
        req=req,
        code_map=code_map,
        selected_modules=selected_modules,
        max_methods_per_module=5,
    )
    
    prompt_tokens = count_prompt_tokens(
    llm,
    SYSTEM_PROMPT,
    user_prompt)

    if prompt_tokens:
        print(
            f"[INFO] Prompt tokens thực tế: "
            f"{prompt_tokens:,}"
        )

    total_prompt_chars = (
        len(SYSTEM_PROMPT)
        + len(user_prompt)
    )

    print(
        f"[INFO] User prompt: {len(user_prompt):,} ký tự"
    )
    print(
        f"[INFO] System + user: "
        f"{total_prompt_chars:,} ký tự"
    )
    print(
        "[INFO] Chưa bao gồm token của structured output schema"
    )

    t2 = time.time()

    result = structured_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])

    t3 = time.time()

    print(
        f"[TIME] Gemini impact_based: "
        f"{t3 - t2:.2f}s"
    )
    print(
        f"[TIME] Tổng: {t3 - t0:.2f}s"
    )

    result_dict = result.model_dump()
    result_dict["mode"] = "impact_based"

    for i, unit_process in enumerate(
        result_dict["unit_processes"],
        start=1,
    ):
        unit_process["no"] = i

    return result_dict


if __name__ == "__main__":
    code_map, index = load_code_map_cached(CODE_MAP_PATH)
    result = break_task(REQUIREMENT_INPUT, code_map, index=index)
    print(json.dumps(result, ensure_ascii=False, indent=2))