import os
import re
import json
import javalang
from pathlib import Path

# Các call thuần framework/tiện ích - không có giá trị cho impact analysis
IGNORE_METHODS = {
    "info", "warn", "error", "debug", "trace",
    "equals", "hashCode", "toString",
    "add", "remove", "contains", "stream", "collect",
    "filter", "map", "forEach", "build", "of", "ok",
    "notFound", "isSuccess", "isEmpty", "isPresent",
}

HTTP_MAPPING_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

# Suffix thường gặp cho class gọi ra hệ thống ngoài
EXTERNAL_CLIENT_SUFFIXES = ("Client", "Gateway", "ApiClient", "FeignClient")


class ProjectAnalyzer:

    def __init__(self, project_path):
        self.project_path = project_path

        self.result = {
            "project": {"name": Path(project_path).name},
            "database": {"db_type": "UNKNOWN"},
            "modules": [],
            "mapper_operations": [],
        }

        # method_id (mapper xml) -> danh sách bảng bị ảnh hưởng
        self.mapper_table_map = {}
        # method_id (mapper xml) -> tên file mapper xml chứa nó
        self.mapper_method_file = {}
        # class_name -> đường dẫn file .java tương đối (dựng ở pass 1)
        self.class_file_map = {}

        self.global_tables = set()

    # =====================================================
    # RUN
    # =====================================================

    def run(self):
        self.detect_database()
        self.scan_mapper_xml()
        self.build_class_file_map()   # pass 1: map class_name -> file
        self.scan_java()              # pass 2: extract module chi tiết

        with open("project-knowledge.json", "w", encoding="utf-8") as f:
            json.dump(self.result, f, ensure_ascii=False, indent=2)

        print("DONE -> project-knowledge.json")

    # =====================================================
    # DATABASE
    # =====================================================

    def detect_database(self):
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file not in ("application.yml", "application.yaml", "application.properties"):
                    continue
                path = os.path.join(root, file)
                try:
                    content = open(path, encoding="utf-8", errors="ignore").read().lower()
                    if "postgresql" in content:
                        self.result["database"]["db_type"] = "PostgreSQL"
                    elif "oracle" in content:
                        self.result["database"]["db_type"] = "Oracle"
                    elif "mysql" in content:
                        self.result["database"]["db_type"] = "MySQL"
                    elif "mariadb" in content:
                        self.result["database"]["db_type"] = "MariaDB"
                except Exception:
                    pass

    # =====================================================
    # MAPPER XML
    # =====================================================

    def scan_mapper_xml(self):
        tags = {"select": "SELECT", "insert": "INSERT", "update": "UPDATE", "delete": "DELETE"}

        for root, _, files in os.walk(self.project_path):
            for file in files:
                if not file.endswith(".xml"):
                    continue

                full_path = os.path.join(root, file)

                try:
                    content = open(full_path, encoding="utf-8", errors="ignore").read()

                    for tag, operation in tags.items():
                        pattern = rf'<{tag}.*?id="([^"]+)".*?>(.*?)</{tag}>'
                        matches = re.findall(pattern, content, re.I | re.S)

                        for method_id, sql in matches:
                            tables = set()
                            for regex in [
                                r'FROM\s+([A-Z0-9_]+)',
                                r'JOIN\s+([A-Z0-9_]+)',
                                r'UPDATE\s+([A-Z0-9_]+)',
                                r'INTO\s+([A-Z0-9_]+)',
                            ]:
                                tables.update(re.findall(regex, sql, re.I))

                            table_list = sorted(tables)

                            self.result["mapper_operations"].append({
                                "mapper": file,
                                "method": method_id,
                                "operation": operation,
                                "tables": table_list,
                            })

                            self.mapper_table_map[method_id] = table_list
                            self.mapper_method_file[method_id] = file
                            self.global_tables.update(table_list)

                except Exception as ex:
                    print(f"[XML ERROR] {full_path}")
                    print(ex)

    # =====================================================
    # PASS 1 - MAP CLASS NAME -> FILE (để dựng related_files)
    # =====================================================

    def build_class_file_map(self):
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if not file.endswith(".java"):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.project_path).replace("\\", "/")

                try:
                    content = open(full_path, encoding="utf-8", errors="ignore").read()
                    tree = javalang.parse.parse(content)

                    for _, cls in tree.filter(javalang.tree.ClassDeclaration):
                        self.class_file_map[cls.name] = rel_path

                except Exception:
                    # Lỗi parse sẽ được log lại chi tiết ở pass 2 (scan_java)
                    pass

    # =====================================================
    # PASS 2 - JAVA
    # =====================================================

    def scan_java(self):
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if not file.endswith(".java"):
                    continue

                full_path = os.path.join(root, file)

                try:
                    self.parse_java(full_path)
                except Exception as ex:
                    print(f"[JAVA ERROR] {full_path}")
                    print(ex)

    def parse_java(self, file_path):
        content = open(file_path, encoding="utf-8", errors="ignore").read()
        tree = javalang.parse.parse(content)

        package_name = tree.package.name if tree.package else ""
        rel_path = os.path.relpath(file_path, self.project_path).replace("\\", "/")

        for _, cls in tree.filter(javalang.tree.ClassDeclaration):
            self.extract_module(cls, rel_path, package_name)

    # =====================================================
    # HELPERS: TYPE / ANNOTATION
    # =====================================================

    def type_to_str(self, t):
        """Chuyển 1 node type của javalang thành string, có hỗ trợ generic: ResponseEntity<Foo>."""
        if t is None:
            return "void"

        name = t.name

        args = getattr(t, "arguments", None)
        if args:
            arg_strs = []
            for arg in args:
                if arg is None:
                    arg_strs.append("?")
                elif getattr(arg, "type", None) is not None:
                    arg_strs.append(self.type_to_str(arg.type))
                else:
                    arg_strs.append("?")
            if arg_strs:
                name = f"{name}<{', '.join(arg_strs)}>"

        dims = getattr(t, "dimensions", None)
        if dims:
            name += "[]" * len(dims)

        return name

    def extract_annotation_values(self, annotation):
        """Lấy toàn bộ literal/enum-member trong 1 annotation (vd path, RequestMethod.POST)."""
        values = []

        def handle(e):
            if e is None:
                return
            if isinstance(e, list):
                for x in e:
                    handle(x)
                return
            if isinstance(e, javalang.tree.ElementValuePair):
                handle(e.value)
                return
            if isinstance(e, javalang.tree.ElementArrayValue):
                for v in e.values:
                    handle(v)
                return
            if isinstance(e, javalang.tree.Literal):
                values.append(str(e.value).strip('"'))
                return
            if isinstance(e, javalang.tree.MemberReference):
                values.append(e.member)
                return

        handle(annotation.element)
        return values

    def combine_path(self, base, path):
        base = (base or "").strip()
        path = (path or "").strip()
        combined = (base.rstrip("/") + "/" + path.lstrip("/")).replace("//", "/")
        if not combined.startswith("/"):
            combined = "/" + combined
        if len(combined) > 1:
            combined = combined.rstrip("/")
        return combined or "/"

    def get_class_base_path(self, cls):
        for ann in cls.annotations:
            if ann.name == "RequestMapping":
                values = self.extract_annotation_values(ann)
                paths = [v for v in values if v not in ("GET", "POST", "PUT", "DELETE", "PATCH")]
                if paths:
                    return paths[0]
        return ""

    def get_endpoint(self, method, class_base_path):
        for ann in method.annotations:
            if ann.name in HTTP_MAPPING_ANNOTATIONS:
                http_method = HTTP_MAPPING_ANNOTATIONS[ann.name]
                values = self.extract_annotation_values(ann)
                path = values[0] if values else ""
                return f"{http_method} {self.combine_path(class_base_path, path)}"

            if ann.name == "RequestMapping":
                values = self.extract_annotation_values(ann)
                http_candidates = [v for v in values if v in ("GET", "POST", "PUT", "DELETE", "PATCH")]
                paths = [v for v in values if v not in ("GET", "POST", "PUT", "DELETE", "PATCH")]
                http_method = http_candidates[0] if http_candidates else "ANY"
                path = paths[0] if paths else ""
                return f"{http_method} {self.combine_path(class_base_path, path)}"

        return None

    # =====================================================
    # MODULE TYPE (giữ nguyên logic gốc)
    # =====================================================

    def detect_module_type(self, cls_name, annotations):
        if "RestController" in annotations:
            return "Controller"
        if "Service" in annotations:
            return "Service"
        if "Repository" in annotations:
            return "Repository"
        if "Entity" in annotations:
            return "Entity"
        if "Component" in annotations:
            return "Component"
        if "Batch" in cls_name:
            return "Batch"
        return "Unknown"

    # =====================================================
    # SUMMARY (heuristic - nên để AI ở bước impact analysis viết lại cho tự nhiên hơn)
    # =====================================================

    def build_summary(self, cls, module_type, endpoints, method_names):
        doc = getattr(cls, "documentation", None)
        if doc:
            first_line = doc.strip().strip("/*").strip("*").split("\n")[0].strip()
            if first_line:
                return first_line

        if module_type == "Controller" and endpoints:
            return "Expose endpoint: " + "; ".join(endpoints)

        if method_names:
            preview = ", ".join(method_names[:3])
            return f"{module_type} class - main methods: {preview}"

        return f"{module_type} class {cls.name}"

    # =====================================================
    # MODULE EXTRACTION
    # =====================================================

    def extract_module(self, cls, file_path, package_name):
        annotations = [a.name for a in cls.annotations]
        module_type = self.detect_module_type(cls.name, annotations)
        class_base_path = self.get_class_base_path(cls) if module_type == "Controller" else ""

        # field_name -> field_type, dùng để phân biệt call vào dependency thật (calls_to_internal)
        # với call vào biến local / framework (bị loại bỏ)
        field_var_types = {}
        dependencies = set()

        for field in cls.fields:
            try:
                type_name = field.type.name
            except Exception:
                continue

            dependencies.add(type_name)
            for decl in field.declarators:
                field_var_types[decl.name] = type_name

        method_names_in_class = {m.name for m in cls.methods}

        source_methods = []
        class_level_tables = set()
        external_integrations = set()
        all_endpoints = []

        for method in cls.methods:
            calls_internal = []
            affected_tables = set()

            try:
                for _, node in method:
                    if not isinstance(node, javalang.tree.MethodInvocation):
                        continue

                    method_name = node.member
                    if method_name in IGNORE_METHODS:
                        continue
                    if method_name.startswith("get") or method_name.startswith("set"):
                        continue

                    qualifier = getattr(node, "qualifier", None)

                    if qualifier and qualifier in field_var_types:
                        # Gọi vào 1 dependency đã inject -> tính là internal call thật
                        dep_type = field_var_types[qualifier]
                        calls_internal.append(f"{dep_type}.{method_name}")

                        if dep_type.endswith(EXTERNAL_CLIENT_SUFFIXES):
                            external_integrations.add(dep_type)

                    elif not qualifier and method_name in method_names_in_class and method_name != method.name:
                        # Gọi method khác trong cùng class
                        calls_internal.append(f"{cls.name}.{method_name}")

                    else:
                        # Gọi framework / biến local (ResponseEntity.ok, resp.put, build...) -> bỏ qua
                        pass

                    # Nếu method này khớp với 1 mapper method đã quét từ XML -> gắn bảng bị ảnh hưởng
                    if method_name in self.mapper_table_map:
                        affected_tables.update(self.mapper_table_map[method_name])

            except Exception:
                pass

            endpoint = self.get_endpoint(method, class_base_path)
            if endpoint:
                all_endpoints.append(endpoint)

            params = [self.type_to_str(p.type) for p in method.parameters]
            returns = self.type_to_str(method.return_type)

            class_level_tables.update(affected_tables)

            source_methods.append({
                "name": method.name,
                "endpoint": endpoint,
                "params": params,
                "returns": returns,
                "calls_to_internal": sorted(set(calls_internal)),
                "affected_tables": sorted(affected_tables),
            })

        # related_files: file của các dependency + file mapper xml đã dùng
        related_files = set()
        for dep_type in dependencies:
            if dep_type in self.class_file_map:
                related_files.add(self.class_file_map[dep_type])

        for m in source_methods:
            for table in m["affected_tables"]:
                for method_id, mapper_file in self.mapper_method_file.items():
                    if table in self.mapper_table_map.get(method_id, []):
                        related_files.add(mapper_file)

        summary = self.build_summary(
            cls, module_type, all_endpoints, [m["name"] for m in source_methods]
        )

        module = {
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "module_name": cls.name,
            "module_type": module_type,
            "summary": summary,
            "source_class": cls.name,
            "source_methods": source_methods,
            "dependencies": sorted(dependencies),
            "tables": sorted(class_level_tables),
            "external_integrations": sorted(external_integrations),
            "related_files": sorted(related_files),
        }

        self.result["modules"].append(module)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyzer.py <project-path>")
        exit()

    analyzer = ProjectAnalyzer(sys.argv[1])
    analyzer.run()