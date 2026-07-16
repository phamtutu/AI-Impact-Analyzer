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

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage


# ============================================================
# CONFIG
# ============================================================

GOOGLE_API_KEY = ""
CODE_MAP_PATH = "project-knowledge.json"

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
    doc_tokens = {}
    df = Counter()
    table_to_modules = {}  # tên bảng (nguyên văn, in hoa) -> set module_name có đụng bảng đó

    for module in code_map["modules"]:
        name = module["module_name"]
        name_to_module[name] = module

        tokens = set()
        tokens |= _tokenize(name)
        tokens |= _tokenize(module.get("summary", ""))
        for method in module["source_methods"]:
            tokens |= _tokenize(method["name"])
        doc_tokens[name] = tokens

        for t in tokens:
            df[t] += 1

        for table in module.get("tables", []):
            table_to_modules.setdefault(table, set()).add(name)

    # Danh sách tất cả tên bảng thật trong database_schema - dùng để match trực tiếp,
    # KHÔNG qua tokenize (tránh vỡ thành "corp"/"wired"/"mnp" gây over-match như đã gặp)
    all_table_names = [t["name"] for t in code_map.get("database_schema", {}).get("tables", [])]

    return {
        "name_to_module": name_to_module,
        "doc_tokens": doc_tokens,
        "df": df,
        "total_modules": len(name_to_module),
        "table_to_modules": table_to_modules,
        "all_table_names": all_table_names,
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
                       max_modules=30, min_relative_score=0.15):
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
Bạn là một trợ lý phân tích nghiệp vụ, viết tài liệu "Định nghĩa Unit Process" (단위 프로세스 정의)
cho hệ thống viễn thông, dựa vào Code Map + Database Schema (JSON) được cung cấp.
Bạn CHỈ dựa vào dữ liệu được cung cấp, KHÔNG tự bịa module/method/bảng/cột không có trong dữ liệu.
KHÔNG ước lượng effort/số giờ - đó không phải nhiệm vụ của bạn ở bước này.

Input requirement có cấu trúc rõ ràng (title/change_type/current_behavior/expected_behavior/
business_rules) - PHẢI dựa vào ĐÚNG các trường này để xác định phạm vi, đặc biệt:
- change_type quyết định mức độ breakdown (tính năng mới cần đủ tầng API/Service/DB từ đầu;
  sửa tính năng có sẵn cần tập trung vào phần current_behavior khác expected_behavior ra sao).
- business_rules PHẢI được thể hiện rõ trong ít nhất 1 unit process tương ứng (không được bỏ sót).

Cấu trúc cần điền cho mỗi unit process:
- level1/level2/level3/level4: phân cấp nghiệp vụ như mô tả
- description: PHẢI liệt kê tên bảng + cột thật (lấy từ affected_columns/database_schema được cung cấp)
- dev_type, process_type (PHẢI trong {PROCESS_TYPES}), function_type (PHẢI trong {FUNCTION_TYPES})
- related_methods: dùng đúng giá trị method_key có sẵn trong Code Map, không tự ghép chuỗi

Nhiệm vụ:
1. Xác định module nào bị ảnh hưởng TRỰC TIẾP và GIÁN TIẾP.
2. Với mỗi thay đổi cần làm, sinh ra 1 dòng unit process đầy đủ các trường trên.
3. Mỗi unit process tương ứng với 1 hành vi nghiệp vụ rõ ràng, không gộp nhiều hành vi vào 1 dòng.
"""


def build_user_prompt(req: RequirementInput, code_map, filtered_modules):
    slim_modules = []
    for m in filtered_modules:
        slim_modules.append({
            "module_name": m["module_name"],
            "module_type": m["module_type"],
            "summary": m.get("summary", ""),
            "source_methods": [
                {
                    "name": mm["name"],
                    "method_key": mm.get("method_key"),
                    "endpoint": mm.get("endpoint"),
                    "calls_to_internal": mm.get("calls_to_internal", []),
                    "affected_tables": mm.get("affected_tables", []),
                    "affected_columns": mm.get("affected_columns", {}),
                }
                for mm in m["source_methods"]
            ],
            "dependencies": m.get("dependencies", []),
            "external_integrations": m.get("external_integrations", []),
        })

    relevant_schema = get_relevant_schema(code_map, filtered_modules)

    return f"""YÊU CẦU NGHIỆP VỤ:
{requirement_to_prompt_text(req)}

CODE MAP (đã lọc, chỉ gồm module nghi ngờ liên quan):
{json.dumps(slim_modules, ensure_ascii=False, indent=2)}

DATABASE SCHEMA (chỉ các bảng liên quan tới module ở trên):
{json.dumps(relevant_schema, ensure_ascii=False, indent=2)}
"""


def build_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        temperature=0.2,
        timeout=30,
        thinking_level="low",
    )


def break_task(req: RequirementInput, code_map, llm=None, index=None):
    if isinstance(req, dict):
        req = RequirementInput(**req)

    search_text = requirement_to_search_text(req)

    t0 = time.time()
    filtered_modules = rule_based_filter(search_text, code_map, index=index)
    t1 = time.time()
    print(f"[TIME] rule_based_filter: {t1 - t0:.2f}s -> {len(filtered_modules)} module: "
          f"{[m['module_name'] for m in filtered_modules]}")

    llm = llm or build_llm()

    # ==================================================
    # CASE 1: KHÔNG TÌM THẤY IMPACT
    # ==================================================
    if not filtered_modules:
        print("[INFO] Không tìm thấy module liên quan -> Requirement Based Mode")

        generic_prompt = f"""
YÊU CẦU NGHIỆP VỤ:
{requirement_to_prompt_text(req)}

Không tìm thấy module nào liên quan trong Code Map hiện có - đây là chức năng HOÀN TOÀN MỚI.

Hãy:
1. Phân tích requirement (đặc biệt chú ý change_type, business_rules).
2. Suy luận các unit process có khả năng cần phát triển theo đúng cấu trúc đã mô tả.
3. process_type PHẢI chọn đúng 1 trong {PROCESS_TYPES}; function_type PHẢI chọn đúng 1 trong {FUNCTION_TYPES}.
4. Để module="" và related_methods=[] vì đây là code hoàn toàn mới, chưa tồn tại.
5. KHÔNG nói các unit process chung chung như "Phân tích yêu cầu"/"Code"/"Unit Test".
6. impacted_modules để rỗng [].
"""
        structured_llm = llm.with_structured_output(BreakdownResult)

        t2 = time.time()
        result = structured_llm.invoke([HumanMessage(content=generic_prompt)])
        t3 = time.time()
        print(f"[TIME] Gọi Gemini (requirement_based): {t3 - t2:.2f}s")

        result_dict = result.model_dump()
        result_dict["mode"] = "requirement_based"
        for i, up in enumerate(result_dict["unit_processes"], start=1):
            up["no"] = i
        return result_dict

    # ==================================================
    # CASE 2: TÌM THẤY IMPACT
    # ==================================================
    print(f"[INFO] Impact mode - match {len(filtered_modules)} modules")

    structured_llm = llm.with_structured_output(BreakdownResult)
    user_prompt = build_user_prompt(req, code_map, filtered_modules)
    print(f"[TIME] Kích thước prompt: {len(user_prompt):,} ký tự (~{len(user_prompt)//4:,} token ước tính)")

    t2 = time.time()
    result = structured_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])
    t3 = time.time()
    print(f"[TIME] Gọi Gemini (structured, impact_based): {t3 - t2:.2f}s")
    print(f"[TIME] TỔNG: {t3 - t0:.2f}s")

    result_dict = result.model_dump()
    result_dict["mode"] = "impact_based"
    for i, up in enumerate(result_dict["unit_processes"], start=1):
        up["no"] = i
    return result_dict


if __name__ == "__main__":
    code_map, index = load_code_map_cached(CODE_MAP_PATH)
    result = break_task(REQUIREMENT_INPUT, code_map, index=index)
    print(json.dumps(result, ensure_ascii=False, indent=2))