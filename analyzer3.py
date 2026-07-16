import os
import re
import sys
import json
import html
import javalang
import xml.etree.ElementTree as ET

from pathlib import Path
from collections import defaultdict


# =========================================================
# CONFIGURATION
# =========================================================

IGNORE_METHODS = {
    "info", "warn", "error", "debug", "trace",
    "equals", "hashCode", "toString",
    "add", "addAll", "remove", "removeAll", "contains",
    "stream", "collect", "filter", "map", "flatMap",
    "forEach", "build", "of", "ok", "body",
    "notFound", "isSuccess", "isEmpty", "isPresent",
    "orElse", "orElseGet", "orElseThrow",
    "get", "set", "size", "length",
    "println", "print", "format",
    "valueOf", "parseLong", "parseInt",
}

HTTP_MAPPING_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

EXTERNAL_CLIENT_SUFFIXES = (
    "Client",
    "Gateway",
    "ApiClient",
    "FeignClient",
)

REPOSITORY_SUFFIXES = (
    "Repository",
    "Mapper",
    "Dao",
    "DAO",
)

JPA_REPOSITORY_TYPES = {
    "JpaRepository",
    "CrudRepository",
    "PagingAndSortingRepository",
    "ListCrudRepository",
    "ListPagingAndSortingRepository",
    "Repository",
}


# =========================================================
# ANALYZER
# =========================================================

class ProjectAnalyzer:

    def __init__(self, project_path):
        self.project_path = os.path.abspath(project_path)

        self.result = {
            "project": {
                "name": Path(self.project_path).name,
                "path": self.project_path,
            },
            "database": {
                "db_type": "UNKNOWN",
            },
            "database_schema": {
                "tables": [],
            },
            "modules": [],
            "mapper_operations": [],
        }

        # class name -> relative java file
        self.class_file_map = {}

        # class name -> package
        self.class_package_map = {}

        # entity class -> entity metadata
        self.entity_metadata = {}

        # table normalized name -> table metadata
        self.table_metadata = {}

        # mapper full key: MapperClass.method -> operation
        self.mapper_operation_map = {}

        # fallback: method name -> list operation
        self.mapper_method_index = defaultdict(list)

        # repository full key: RepositoryClass.method -> operation
        self.repository_operation_map = {}

        # Repository class -> Entity class
        self.repository_entity_map = {}

        # module name -> module result
        self.module_map = {}

        # Class.method -> source method dictionary
        self.method_result_map = {}

        # Class.method -> called Class.method keys
        self.call_graph = defaultdict(set)

        self.global_tables = set()

    # =====================================================
    # RUN
    # =====================================================

    def run(self):
        print("[1/8] Detecting database...")
        self.detect_database()

        print("[2/8] Building Java class index...")
        self.build_class_file_map()

        print("[3/8] Scanning JPA entities...")
        self.scan_jpa_entities()

        print("[4/8] Scanning MyBatis XML...")
        self.scan_mapper_xml()

        print("[5/8] Scanning repositories...")
        self.scan_repositories()

        print("[6/8] Scanning Java modules...")
        self.scan_java_modules()

        print("[7/8] Propagating table impacts...")
        self.propagate_table_impacts()

        print("[8/8] Finalizing result...")
        self.finalize_result()

        output_path = os.path.join(os.getcwd(), "project-knowledge.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                self.result,
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"DONE -> {output_path}")

    # =====================================================
    # FILE HELPERS
    # =====================================================

    def read_file(self, path):
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def relative_path(self, full_path):
        return os.path.relpath(
            full_path,
            self.project_path,
        ).replace("\\", "/")

    def find_files(self, extensions):
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [
                d for d in dirs
                if d not in {
                    ".git",
                    ".idea",
                    ".gradle",
                    "target",
                    "build",
                    "node_modules",
                }
            ]

            for file in files:
                if file.endswith(extensions):
                    yield os.path.join(root, file)

    # =====================================================
    # DATABASE
    # =====================================================

    def detect_database(self):
        config_names = {
            "application.yml",
            "application.yaml",
            "application.properties",
            "bootstrap.yml",
            "bootstrap.yaml",
            "bootstrap.properties",
        }

        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file not in config_names:
                    continue

                path = os.path.join(root, file)

                try:
                    content = self.read_file(path).lower()

                    if "postgresql" in content:
                        self.result["database"]["db_type"] = "PostgreSQL"
                    elif "oracle" in content:
                        self.result["database"]["db_type"] = "Oracle"
                    elif "mariadb" in content:
                        self.result["database"]["db_type"] = "MariaDB"
                    elif "mysql" in content:
                        self.result["database"]["db_type"] = "MySQL"
                    elif "sqlserver" in content or "mssql" in content:
                        self.result["database"]["db_type"] = "SQL Server"
                    elif "h2:" in content:
                        self.result["database"]["db_type"] = "H2"

                except Exception as ex:
                    print(f"[CONFIG ERROR] {path}: {ex}")

    # =====================================================
    # JAVA CLASS INDEX
    # =====================================================

    def build_class_file_map(self):
        for full_path in self.find_files((".java",)):
            rel_path = self.relative_path(full_path)

            try:
                content = self.read_file(full_path)
                tree = javalang.parse.parse(content)

                package_name = tree.package.name if tree.package else ""

                declarations = []

                declarations.extend(
                    node
                    for _, node in tree.filter(
                        javalang.tree.ClassDeclaration
                    )
                )

                declarations.extend(
                    node
                    for _, node in tree.filter(
                        javalang.tree.InterfaceDeclaration
                    )
                )

                declarations.extend(
                    node
                    for _, node in tree.filter(
                        javalang.tree.EnumDeclaration
                    )
                )

                for declaration in declarations:
                    self.class_file_map[declaration.name] = rel_path
                    self.class_package_map[declaration.name] = package_name

            except Exception as ex:
                print(f"[INDEX WARNING] {rel_path}: {ex}")

    # =====================================================
    # ANNOTATION HELPERS
    # =====================================================

    def annotation_name(self, annotation):
        return annotation.name.split(".")[-1]

    def find_annotation(self, annotations, name):
        for annotation in annotations or []:
            if self.annotation_name(annotation) == name:
                return annotation
        return None

    def has_annotation(self, annotations, name):
        return self.find_annotation(annotations, name) is not None

    def expression_to_value(self, expression):
        if expression is None:
            return None

        if isinstance(expression, javalang.tree.Literal):
            value = str(expression.value)

            if (
                len(value) >= 2
                and value[0] == '"'
                and value[-1] == '"'
            ):
                value = value[1:-1]

            return value

        if isinstance(expression, javalang.tree.MemberReference):
            if expression.qualifier:
                return f"{expression.qualifier}.{expression.member}"
            return expression.member

        if isinstance(expression, javalang.tree.ClassReference):
            return self.type_to_str(expression.type)

        if isinstance(expression, javalang.tree.BinaryOperation):
            left = self.expression_to_value(expression.operandl) or ""
            right = self.expression_to_value(expression.operandr) or ""

            if expression.operator == "+":
                return left + right

            return f"{left}{expression.operator}{right}"

        if isinstance(expression, javalang.tree.ElementArrayValue):
            return [
                self.expression_to_value(value)
                for value in expression.values
            ]

        if isinstance(expression, list):
            return [
                self.expression_to_value(value)
                for value in expression
            ]

        return str(expression)

    def annotation_attributes(self, annotation):
        result = {}

        if annotation is None:
            return result

        element = annotation.element

        if element is None:
            return result

        if isinstance(element, list):
            for item in element:
                if isinstance(item, javalang.tree.ElementValuePair):
                    result[item.name] = self.expression_to_value(item.value)

        elif isinstance(element, javalang.tree.ElementValuePair):
            result[element.name] = self.expression_to_value(element.value)

        else:
            result["value"] = self.expression_to_value(element)

        return result

    def annotation_value(self, annotation, names=("name", "value")):
        attributes = self.annotation_attributes(annotation)

        for name in names:
            value = attributes.get(name)

            if isinstance(value, list):
                return value[0] if value else None

            if value not in (None, ""):
                return value

        return None

    def annotation_boolean(self, annotation, name, default=False):
        attributes = self.annotation_attributes(annotation)
        value = attributes.get(name)

        if value is None:
            return default

        return str(value).lower() == "true"

    # =====================================================
    # TYPE HELPERS
    # =====================================================

    def type_to_str(self, java_type):
        if java_type is None:
            return "void"

        name = getattr(java_type, "name", None)

        if not name:
            return str(java_type)

        sub_type = getattr(java_type, "sub_type", None)

        while sub_type is not None:
            name += "." + sub_type.name
            sub_type = getattr(sub_type, "sub_type", None)

        arguments = getattr(java_type, "arguments", None)

        if arguments:
            argument_strings = []

            for argument in arguments:
                if argument is None:
                    argument_strings.append("?")
                    continue

                argument_type = getattr(argument, "type", None)

                if argument_type is not None:
                    argument_strings.append(
                        self.type_to_str(argument_type)
                    )
                else:
                    pattern_type = getattr(argument, "pattern_type", None)

                    if pattern_type:
                        argument_strings.append(str(pattern_type))
                    else:
                        argument_strings.append("?")

            name += f"<{', '.join(argument_strings)}>"

        dimensions = getattr(java_type, "dimensions", None)

        if dimensions:
            name += "[]" * len(dimensions)

        return name

    def get_simple_type_name(self, type_name):
        if not type_name:
            return type_name

        type_name = re.sub(r"<.*>", "", type_name)
        return type_name.split(".")[-1]

    # =====================================================
    # TABLE METADATA
    # =====================================================

    def normalize_identifier(self, identifier):
        if not identifier:
            return None

        identifier = html.unescape(str(identifier))
        identifier = identifier.strip()

        identifier = identifier.replace("`", "")
        identifier = identifier.replace('"', "")
        identifier = identifier.replace("[", "")
        identifier = identifier.replace("]", "")

        identifier = re.sub(r"\s+", " ", identifier)

        return identifier.strip()

    def normalize_table_key(self, table_name):
        normalized = self.normalize_identifier(table_name)

        if not normalized:
            return None

        return normalized.lower()

    def register_table(
        self,
        table_name,
        source_type,
        source_file=None,
        entity_class=None,
        mapper=None,
        columns=None,
    ):
        table_name = self.normalize_identifier(table_name)

        if not table_name:
            return

        key = self.normalize_table_key(table_name)

        if key not in self.table_metadata:
            self.table_metadata[key] = {
                "name": table_name,
                "sources": [],
                "entity_classes": [],
                "mappers": [],
                "columns": [],
            }

        table = self.table_metadata[key]

        source = {
            "type": source_type,
            "file": source_file,
        }

        if source not in table["sources"]:
            table["sources"].append(source)

        if entity_class and entity_class not in table["entity_classes"]:
            table["entity_classes"].append(entity_class)

        if mapper and mapper not in table["mappers"]:
            table["mappers"].append(mapper)

        for column in columns or []:
            self.register_column(table_name, column)

        self.global_tables.add(table_name)

    def register_column(self, table_name, column):
        if not table_name or not column:
            return

        key = self.normalize_table_key(table_name)

        if key not in self.table_metadata:
            self.register_table(
                table_name=table_name,
                source_type="INFERRED",
            )

        table = self.table_metadata[key]

        if isinstance(column, str):
            column = {
                "name": column,
            }

        column_name = self.normalize_identifier(column.get("name"))

        if not column_name:
            return

        if column_name == "*" or "(" in column_name:
            return

        normalized_column = {
            "name": column_name,
            "property": column.get("property"),
            "java_type": column.get("java_type"),
            "primary_key": bool(column.get("primary_key", False)),
            "nullable": column.get("nullable"),
            "unique": column.get("unique"),
            "insertable": column.get("insertable"),
            "updatable": column.get("updatable"),
            "relationship": column.get("relationship"),
            "source": column.get("source"),
        }

        existing = None

        for current_column in table["columns"]:
            if current_column["name"].lower() == column_name.lower():
                existing = current_column
                break

        if existing is None:
            table["columns"].append(normalized_column)
        else:
            for field, value in normalized_column.items():
                if value is not None and value is not False:
                    existing[field] = value

            if normalized_column["primary_key"]:
                existing["primary_key"] = True

    # =====================================================
    # JPA ENTITY SCANNING
    # =====================================================

    def scan_jpa_entities(self):
        for full_path in self.find_files((".java",)):
            rel_path = self.relative_path(full_path)

            try:
                content = self.read_file(full_path)
                tree = javalang.parse.parse(content)

                for _, cls in tree.filter(
                    javalang.tree.ClassDeclaration
                ):
                    annotations = cls.annotations or []

                    if not self.has_annotation(annotations, "Entity"):
                        continue

                    table_annotation = self.find_annotation(
                        annotations,
                        "Table",
                    )

                    table_name = self.annotation_value(
                        table_annotation,
                        ("name", "value"),
                    )

                    schema_name = self.annotation_value(
                        table_annotation,
                        ("schema",),
                    )

                    if not table_name:
                        table_name = self.camel_to_snake(cls.name)

                    full_table_name = (
                        f"{schema_name}.{table_name}"
                        if schema_name
                        else table_name
                    )

                    columns = []

                    for field in cls.fields:
                        field_annotations = field.annotations or []

                        if self.has_annotation(
                            field_annotations,
                            "Transient",
                        ):
                            continue

                        column_annotation = self.find_annotation(
                            field_annotations,
                            "Column",
                        )

                        join_column_annotation = self.find_annotation(
                            field_annotations,
                            "JoinColumn",
                        )

                        embedded_annotation = self.find_annotation(
                            field_annotations,
                            "Embedded",
                        )

                        if embedded_annotation:
                            continue

                        is_id = (
                            self.has_annotation(field_annotations, "Id")
                            or self.has_annotation(
                                field_annotations,
                                "EmbeddedId",
                            )
                        )

                        relationship = self.detect_relationship(
                            field_annotations
                        )

                        for declarator in field.declarators:
                            property_name = declarator.name

                            column_name = self.annotation_value(
                                column_annotation,
                                ("name", "value"),
                            )

                            if not column_name:
                                column_name = self.annotation_value(
                                    join_column_annotation,
                                    ("name", "value"),
                                )

                            if not column_name:
                                column_name = self.camel_to_snake(
                                    property_name
                                )

                            nullable = None
                            unique = None
                            insertable = None
                            updatable = None

                            if column_annotation:
                                attrs = self.annotation_attributes(
                                    column_annotation
                                )

                                if "nullable" in attrs:
                                    nullable = (
                                        str(attrs["nullable"]).lower()
                                        == "true"
                                    )

                                if "unique" in attrs:
                                    unique = (
                                        str(attrs["unique"]).lower()
                                        == "true"
                                    )

                                if "insertable" in attrs:
                                    insertable = (
                                        str(attrs["insertable"]).lower()
                                        == "true"
                                    )

                                if "updatable" in attrs:
                                    updatable = (
                                        str(attrs["updatable"]).lower()
                                        == "true"
                                    )

                            columns.append({
                                "name": column_name,
                                "property": property_name,
                                "java_type": self.type_to_str(field.type),
                                "primary_key": is_id,
                                "nullable": nullable,
                                "unique": unique,
                                "insertable": insertable,
                                "updatable": updatable,
                                "relationship": relationship,
                                "source": "JPA",
                            })

                    metadata = {
                        "entity_class": cls.name,
                        "table": full_table_name,
                        "file": rel_path,
                        "columns": columns,
                    }

                    self.entity_metadata[cls.name] = metadata

                    self.register_table(
                        table_name=full_table_name,
                        source_type="JPA_ENTITY",
                        source_file=rel_path,
                        entity_class=cls.name,
                        columns=columns,
                    )

            except Exception as ex:
                print(f"[JPA ERROR] {rel_path}: {ex}")

    def detect_relationship(self, annotations):
        relationships = [
            "ManyToOne",
            "OneToMany",
            "OneToOne",
            "ManyToMany",
        ]

        for relationship in relationships:
            if self.has_annotation(annotations, relationship):
                return relationship

        return None

    def camel_to_snake(self, name):
        if not name:
            return name

        value = re.sub(
            r"(.)([A-Z][a-z]+)",
            r"\1_\2",
            name,
        )

        value = re.sub(
            r"([a-z0-9])([A-Z])",
            r"\1_\2",
            value,
        )

        return value.lower()

    # =====================================================
    # SQL ANALYSIS
    # =====================================================

    def clean_sql(self, sql):
        if not sql:
            return ""

        sql = html.unescape(sql)

        sql = re.sub(
            r"/\*.*?\*/",
            " ",
            sql,
            flags=re.S,
        )

        sql = re.sub(
            r"--[^\r\n]*",
            " ",
            sql,
        )

        sql = re.sub(
            r"<[^>]+>",
            " ",
            sql,
        )

        sql = re.sub(
            r"\s+",
            " ",
            sql,
        )

        return sql.strip()

    def extract_sql_tables(self, sql):
        sql = self.clean_sql(sql)
        tables = set()

        identifier = (
            r'(?:[`"\[]?[A-Za-z_][A-Za-z0-9_$]*[`"\]]?)'
            r'(?:\s*\.\s*'
            r'(?:[`"\[]?[A-Za-z_][A-Za-z0-9_$]*[`"\]]?))?'
        )

        patterns = [
            rf"\bFROM\s+({identifier})",
            rf"\bJOIN\s+({identifier})",
            rf"\bUPDATE\s+({identifier})",
            rf"\bINSERT\s+INTO\s+({identifier})",
            rf"\bDELETE\s+FROM\s+({identifier})",
            rf"\bMERGE\s+INTO\s+({identifier})",
        ]

        ignored = {
            "select",
            "values",
            "set",
            "dual",
        }

        for pattern in patterns:
            for match in re.findall(pattern, sql, re.I):
                table_name = self.normalize_identifier(match)
                table_name = re.sub(r"\s*\.\s*", ".", table_name)

                if table_name.lower() not in ignored:
                    tables.add(table_name)

        return sorted(tables)

    def extract_sql_aliases(self, sql):
        sql = self.clean_sql(sql)
        aliases = {}

        identifier = (
            r'(?:[`"\[]?[A-Za-z_][A-Za-z0-9_$]*[`"\]]?)'
            r'(?:\s*\.\s*'
            r'(?:[`"\[]?[A-Za-z_][A-Za-z0-9_$]*[`"\]]?))?'
        )

        pattern = (
            rf"\b(?:FROM|JOIN)\s+({identifier})"
            rf"(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_$]*))?"
        )

        sql_keywords = {
            "where", "join", "left", "right", "inner", "outer",
            "full", "cross", "on", "group", "order", "having",
            "limit", "offset", "union", "set",
        }

        for table, alias in re.findall(pattern, sql, re.I):
            table = self.normalize_identifier(table)
            table = re.sub(r"\s*\.\s*", ".", table)

            aliases[table.lower()] = table

            if alias and alias.lower() not in sql_keywords:
                aliases[alias.lower()] = table

        return aliases

    def split_sql_list(self, text):
        if not text:
            return []

        result = []
        current = []
        depth = 0
        quote = None

        for char in text:
            if quote:
                current.append(char)

                if char == quote:
                    quote = None

                continue

            if char in ("'", '"', "`"):
                quote = char
                current.append(char)
                continue

            if char == "(":
                depth += 1
                current.append(char)
                continue

            if char == ")":
                depth = max(0, depth - 1)
                current.append(char)
                continue

            if char == "," and depth == 0:
                value = "".join(current).strip()

                if value:
                    result.append(value)

                current = []
                continue

            current.append(char)

        value = "".join(current).strip()

        if value:
            result.append(value)

        return result

    def extract_sql_columns(self, sql, operation):
        sql = self.clean_sql(sql)
        columns_by_table = defaultdict(set)

        tables = self.extract_sql_tables(sql)
        aliases = self.extract_sql_aliases(sql)

        default_table = tables[0] if len(tables) == 1 else None

        if operation == "SELECT":
            match = re.search(
                r"\bSELECT\s+(.*?)\s+FROM\b",
                sql,
                re.I | re.S,
            )

            if match:
                select_items = self.split_sql_list(match.group(1))

                for item in select_items:
                    item = re.sub(
                        r"\s+AS\s+[A-Za-z_][A-Za-z0-9_$]*$",
                        "",
                        item,
                        flags=re.I,
                    )

                    item = re.sub(
                        r"\s+[A-Za-z_][A-Za-z0-9_$]*$",
                        "",
                        item,
                    )

                    qualified_match = re.match(
                        r"^\s*([A-Za-z_][A-Za-z0-9_$]*)"
                        r"\.([A-Za-z_][A-Za-z0-9_$]*|\*)\s*$",
                        item,
                    )

                    if qualified_match:
                        alias = qualified_match.group(1).lower()
                        column = qualified_match.group(2)
                        table = aliases.get(alias)

                        if table and column != "*":
                            columns_by_table[table].add(column)

                        continue

                    simple_match = re.match(
                        r"^\s*[`\"\[]?"
                        r"([A-Za-z_][A-Za-z0-9_$]*)"
                        r"[`\"\]]?\s*$",
                        item,
                    )

                    if simple_match and default_table:
                        columns_by_table[default_table].add(
                            simple_match.group(1)
                        )

        elif operation == "INSERT":
            match = re.search(
                r"\bINSERT\s+INTO\s+"
                r"(?:[`\"\[]?[A-Za-z_][A-Za-z0-9_$]*[`\"\]]?"
                r"(?:\s*\.\s*"
                r"[`\"\[]?[A-Za-z_][A-Za-z0-9_$]*[`\"\]]?)?)"
                r"\s*\((.*?)\)",
                sql,
                re.I | re.S,
            )

            if match and default_table:
                for column in self.split_sql_list(match.group(1)):
                    column = self.normalize_identifier(column)

                    if re.match(
                        r"^[A-Za-z_][A-Za-z0-9_$]*$",
                        column,
                    ):
                        columns_by_table[default_table].add(column)

        elif operation == "UPDATE":
            match = re.search(
                r"\bSET\s+(.*?)(?:\bWHERE\b|$)",
                sql,
                re.I | re.S,
            )

            if match and default_table:
                assignments = self.split_sql_list(match.group(1))

                for assignment in assignments:
                    column_match = re.match(
                        r"\s*(?:[A-Za-z_][A-Za-z0-9_$]*\.)?"
                        r"[`\"\[]?([A-Za-z_][A-Za-z0-9_$]*)"
                        r"[`\"\]]?\s*=",
                        assignment,
                    )

                    if column_match:
                        columns_by_table[default_table].add(
                            column_match.group(1)
                        )

        # Bổ sung column xuất hiện trong alias.column ở WHERE/JOIN.
        for alias, column in re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_$]*)"
            r"\.([A-Za-z_][A-Za-z0-9_$]*)\b",
            sql,
        ):
            table = aliases.get(alias.lower())

            if table:
                columns_by_table[table].add(column)

        return {
            table: sorted(columns)
            for table, columns in columns_by_table.items()
        }

    # =====================================================
    # MYBATIS XML
    # =====================================================

    def scan_mapper_xml(self):
        for full_path in self.find_files((".xml",)):
            rel_path = self.relative_path(full_path)

            try:
                content = self.read_file(full_path)

                if "<mapper" not in content:
                    continue

                parser = ET.XMLParser()
                root = ET.fromstring(content, parser=parser)

                if self.strip_xml_namespace(root.tag) != "mapper":
                    continue

                namespace = root.attrib.get("namespace", "")
                mapper_class = (
                    namespace.split(".")[-1]
                    if namespace
                    else Path(full_path).stem
                )

                result_map_columns = self.extract_result_maps(root)

                statement_tags = {
                    "select": "SELECT",
                    "insert": "INSERT",
                    "update": "UPDATE",
                    "delete": "DELETE",
                }

                for element in root.iter():
                    tag = self.strip_xml_namespace(element.tag)

                    if tag not in statement_tags:
                        continue

                    method_id = element.attrib.get("id")

                    if not method_id:
                        continue

                    operation = statement_tags[tag]
                    sql = self.xml_element_to_text(element)

                    tables = self.extract_sql_tables(sql)
                    columns_by_table = self.extract_sql_columns(
                        sql,
                        operation,
                    )

                    result_map_id = element.attrib.get("resultMap")

                    if result_map_id:
                        result_map_id = result_map_id.split(".")[-1]
                        mapped_columns = result_map_columns.get(
                            result_map_id,
                            [],
                        )

                        if len(tables) == 1:
                            table_name = tables[0]

                            columns_by_table.setdefault(
                                table_name,
                                [],
                            )

                            columns_by_table[table_name] = sorted(
                                set(columns_by_table[table_name])
                                | {
                                    column["name"]
                                    for column in mapped_columns
                                    if column.get("name")
                                }
                            )

                    mapper_key = f"{mapper_class}.{method_id}"

                    operation_info = {
                        "mapper": os.path.basename(full_path),
                        "mapper_path": rel_path,
                        "namespace": namespace,
                        "mapper_class": mapper_class,
                        "method": method_id,
                        "method_key": mapper_key,
                        "operation": operation,
                        "tables": tables,
                        "columns_by_table": columns_by_table,
                        "sql": sql,
                    }

                    self.result["mapper_operations"].append(
                        operation_info
                    )

                    self.mapper_operation_map[mapper_key] = operation_info
                    self.mapper_method_index[method_id].append(
                        operation_info
                    )

                    for table_name in tables:
                        columns = [
                            {
                                "name": column_name,
                                "source": "MYBATIS_SQL",
                            }
                            for column_name
                            in columns_by_table.get(table_name, [])
                        ]

                        self.register_table(
                            table_name=table_name,
                            source_type="MYBATIS_XML",
                            source_file=rel_path,
                            mapper=mapper_class,
                            columns=columns,
                        )

            except ET.ParseError as ex:
                print(f"[MYBATIS XML PARSE ERROR] {rel_path}: {ex}")

            except Exception as ex:
                print(f"[MYBATIS XML ERROR] {rel_path}: {ex}")

    def strip_xml_namespace(self, tag):
        if "}" in tag:
            return tag.split("}", 1)[1]

        return tag

    def xml_element_to_text(self, element):
        text_parts = []

        def visit(node):
            if node.text:
                text_parts.append(node.text)

            tag = self.strip_xml_namespace(node.tag)

            if tag == "include":
                refid = node.attrib.get("refid")

                if refid:
                    text_parts.append(f" /* include:{refid} */ ")

            for child in list(node):
                visit(child)

                if child.tail:
                    text_parts.append(child.tail)

        visit(element)

        return self.clean_sql(" ".join(text_parts))

    def extract_result_maps(self, root):
        result = {}

        for element in root.iter():
            if self.strip_xml_namespace(element.tag) != "resultMap":
                continue

            result_map_id = element.attrib.get("id")

            if not result_map_id:
                continue

            columns = []

            for child in element.iter():
                tag = self.strip_xml_namespace(child.tag)

                if tag not in {
                    "id",
                    "result",
                    "association",
                    "collection",
                    "arg",
                    "idArg",
                }:
                    continue

                column_name = child.attrib.get("column")
                property_name = child.attrib.get("property")

                if column_name:
                    columns.append({
                        "name": column_name,
                        "property": property_name,
                        "java_type": child.attrib.get("javaType"),
                        "primary_key": tag in {"id", "idArg"},
                        "source": "MYBATIS_RESULT_MAP",
                    })

            result[result_map_id] = columns

        return result

    # =====================================================
    # REPOSITORY ANALYSIS
    # =====================================================

    def scan_repositories(self):
        for full_path in self.find_files((".java",)):
            rel_path = self.relative_path(full_path)

            try:
                content = self.read_file(full_path)
                tree = javalang.parse.parse(content)

                declarations = []

                declarations.extend(
                    node
                    for _, node in tree.filter(
                        javalang.tree.InterfaceDeclaration
                    )
                )

                declarations.extend(
                    node
                    for _, node in tree.filter(
                        javalang.tree.ClassDeclaration
                    )
                )

                for declaration in declarations:
                    repository_name = declaration.name

                    entity_class = self.resolve_repository_entity(
                        declaration
                    )

                    if entity_class:
                        self.repository_entity_map[
                            repository_name
                        ] = entity_class

                    is_repository = (
                        repository_name.endswith(REPOSITORY_SUFFIXES)
                        or self.has_annotation(
                            declaration.annotations or [],
                            "Repository",
                        )
                        or self.has_annotation(
                            declaration.annotations or [],
                            "Mapper",
                        )
                        or entity_class is not None
                    )

                    if not is_repository:
                        continue

                    for method in declaration.methods:
                        key = f"{repository_name}.{method.name}"

                        operation_info = self.analyze_repository_method(
                            repository_name=repository_name,
                            entity_class=entity_class,
                            method=method,
                            source_file=rel_path,
                        )

                        if operation_info:
                            self.repository_operation_map[
                                key
                            ] = operation_info

            except Exception as ex:
                print(f"[REPOSITORY ERROR] {rel_path}: {ex}")

    def resolve_repository_entity(self, declaration):
        for extended_type in declaration.extends or []:
            repository_type = self.get_simple_type_name(
                extended_type.name
            )

            if repository_type not in JPA_REPOSITORY_TYPES:
                continue

            arguments = getattr(extended_type, "arguments", None) or []

            if not arguments:
                continue

            entity_argument = arguments[0]
            entity_type = getattr(entity_argument, "type", None)

            if entity_type is not None:
                return self.get_simple_type_name(
                    self.type_to_str(entity_type)
                )

        return None

    def analyze_repository_method(
        self,
        repository_name,
        entity_class,
        method,
        source_file,
    ):
        annotations = method.annotations or []

        query_annotation = self.find_annotation(
            annotations,
            "Query",
        )

        modifying = self.has_annotation(
            annotations,
            "Modifying",
        )

        tables = set()
        columns_by_table = defaultdict(set)
        operation = self.derive_operation_from_method(method.name)

        if query_annotation:
            query_value = self.annotation_value(
                query_annotation,
                ("value",),
            )

            attributes = self.annotation_attributes(query_annotation)

            native_query = (
                str(attributes.get("nativeQuery", "false")).lower()
                == "true"
            )

            if query_value:
                if native_query:
                    operation = self.detect_sql_operation(query_value)
                    tables.update(self.extract_sql_tables(query_value))

                    extracted_columns = self.extract_sql_columns(
                        query_value,
                        operation,
                    )

                    for table_name, columns in extracted_columns.items():
                        columns_by_table[table_name].update(columns)

                elif entity_class in self.entity_metadata:
                    # JPQL dùng entity name thay vì table name.
                    entity_table = self.entity_metadata[
                        entity_class
                    ]["table"]

                    tables.add(entity_table)

                    for property_name in self.extract_jpql_properties(
                        query_value
                    ):
                        column_name = self.resolve_entity_column(
                            entity_class,
                            property_name,
                        )

                        if column_name:
                            columns_by_table[entity_table].add(
                                column_name
                            )

                    if modifying:
                        operation = self.detect_jpql_operation(
                            query_value
                        )

        elif entity_class in self.entity_metadata:
            table_name = self.entity_metadata[entity_class]["table"]
            tables.add(table_name)

            for property_name in self.extract_derived_query_properties(
                method.name
            ):
                column_name = self.resolve_entity_column(
                    entity_class,
                    property_name,
                )

                if column_name:
                    columns_by_table[table_name].add(column_name)

        # Nếu là MyBatis annotation mapper như @Select/@Update.
        annotation_sql_map = {
            "Select": "SELECT",
            "Insert": "INSERT",
            "Update": "UPDATE",
            "Delete": "DELETE",
        }

        for annotation_name, annotation_operation in (
            annotation_sql_map.items()
        ):
            annotation = self.find_annotation(
                annotations,
                annotation_name,
            )

            if not annotation:
                continue

            sql = self.annotation_value(annotation, ("value",))

            if isinstance(sql, list):
                sql = " ".join(str(value) for value in sql)

            if sql:
                operation = annotation_operation
                tables.update(self.extract_sql_tables(sql))

                extracted_columns = self.extract_sql_columns(
                    sql,
                    operation,
                )

                for table_name, columns in extracted_columns.items():
                    columns_by_table[table_name].update(columns)

        if not tables:
            return None

        operation_info = {
            "repository": repository_name,
            "method": method.name,
            "operation": operation,
            "tables": sorted(tables),
            "columns_by_table": {
                table: sorted(columns)
                for table, columns in columns_by_table.items()
            },
            "source_file": source_file,
            "entity_class": entity_class,
        }

        for table_name in tables:
            columns = [
                {
                    "name": column_name,
                    "source": "JPA_REPOSITORY",
                }
                for column_name
                in columns_by_table.get(table_name, [])
            ]

            self.register_table(
                table_name=table_name,
                source_type="JPA_REPOSITORY",
                source_file=source_file,
                entity_class=entity_class,
                columns=columns,
            )

        return operation_info

    def detect_sql_operation(self, sql):
        sql = self.clean_sql(sql).upper()

        if sql.startswith("SELECT"):
            return "SELECT"
        if sql.startswith("INSERT"):
            return "INSERT"
        if sql.startswith("UPDATE"):
            return "UPDATE"
        if sql.startswith("DELETE"):
            return "DELETE"
        if sql.startswith("MERGE"):
            return "MERGE"

        return "UNKNOWN"

    def detect_jpql_operation(self, query):
        normalized = query.strip().upper()

        if normalized.startswith("UPDATE"):
            return "UPDATE"

        if normalized.startswith("DELETE"):
            return "DELETE"

        if normalized.startswith("INSERT"):
            return "INSERT"

        return "SELECT"

    def derive_operation_from_method(self, method_name):
        lower_name = method_name.lower()

        if lower_name.startswith(
            ("save", "insert", "create", "persist")
        ):
            return "INSERT_OR_UPDATE"

        if lower_name.startswith(
            ("delete", "remove")
        ):
            return "DELETE"

        if lower_name.startswith(
            ("update", "modify")
        ):
            return "UPDATE"

        return "SELECT"

    def extract_jpql_properties(self, query):
        properties = set()

        for _, property_name in re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]*)"
            r"\.([A-Za-z_][A-Za-z0-9_]*)\b",
            query,
        ):
            properties.add(property_name)

        return sorted(properties)

    def extract_derived_query_properties(self, method_name):
        match = re.search(
            r"(?:By)(.+)$",
            method_name,
        )

        if not match:
            return []

        condition = match.group(1)

        condition = re.split(
            r"OrderBy",
            condition,
            maxsplit=1,
        )[0]

        parts = re.split(
            r"And|Or",
            condition,
        )

        operators = [
            "IsNotNull",
            "IsNull",
            "NotIn",
            "Between",
            "LessThanEqual",
            "GreaterThanEqual",
            "LessThan",
            "GreaterThan",
            "StartingWith",
            "EndingWith",
            "Containing",
            "Contains",
            "IgnoreCase",
            "NotLike",
            "Like",
            "Not",
            "In",
            "True",
            "False",
            "Before",
            "After",
            "Equals",
            "Is",
        ]

        properties = []

        for part in parts:
            for operator in operators:
                if part.endswith(operator):
                    part = part[:-len(operator)]
                    break

            if part:
                property_name = part[0].lower() + part[1:]
                properties.append(property_name)

        return properties

    def resolve_entity_column(self, entity_class, property_name):
        entity = self.entity_metadata.get(entity_class)

        if not entity:
            return None

        for column in entity["columns"]:
            if column.get("property") == property_name:
                return column.get("name")

        return self.camel_to_snake(property_name)

    # =====================================================
    # ENDPOINT HELPERS
    # =====================================================

    def extract_annotation_values(self, annotation):
        attributes = self.annotation_attributes(annotation)
        values = []

        for value in attributes.values():
            if isinstance(value, list):
                values.extend(str(item) for item in value)
            elif value is not None:
                values.append(str(value))

        return values

    def combine_path(self, base, path):
        base = (base or "").strip()
        path = (path or "").strip()

        combined = (
            base.rstrip("/") + "/" + path.lstrip("/")
        )

        combined = re.sub(r"/+", "/", combined)

        if not combined.startswith("/"):
            combined = "/" + combined

        if len(combined) > 1:
            combined = combined.rstrip("/")

        return combined or "/"

    def get_class_base_path(self, declaration):
        annotation = self.find_annotation(
            declaration.annotations or [],
            "RequestMapping",
        )

        if not annotation:
            return ""

        attributes = self.annotation_attributes(annotation)

        value = (
            attributes.get("path")
            or attributes.get("value")
            or ""
        )

        if isinstance(value, list):
            return value[0] if value else ""

        return value

    def get_endpoint(self, method, class_base_path):
        for annotation in method.annotations or []:
            annotation_name = self.annotation_name(annotation)

            if annotation_name in HTTP_MAPPING_ANNOTATIONS:
                http_method = HTTP_MAPPING_ANNOTATIONS[
                    annotation_name
                ]

                attributes = self.annotation_attributes(annotation)

                path = (
                    attributes.get("path")
                    or attributes.get("value")
                    or ""
                )

                if isinstance(path, list):
                    path = path[0] if path else ""

                return (
                    f"{http_method} "
                    f"{self.combine_path(class_base_path, path)}"
                )

            if annotation_name == "RequestMapping":
                attributes = self.annotation_attributes(annotation)

                path = (
                    attributes.get("path")
                    or attributes.get("value")
                    or ""
                )

                if isinstance(path, list):
                    path = path[0] if path else ""

                request_method = attributes.get("method")
                http_method = "ANY"

                if isinstance(request_method, list):
                    request_method = (
                        request_method[0]
                        if request_method
                        else None
                    )

                if request_method:
                    http_method = str(request_method).split(".")[-1]

                return (
                    f"{http_method} "
                    f"{self.combine_path(class_base_path, path)}"
                )

        return None

    # =====================================================
    # MODULE ANALYSIS
    # =====================================================

    def scan_java_modules(self):
        for full_path in self.find_files((".java",)):
            rel_path = self.relative_path(full_path)

            try:
                content = self.read_file(full_path)
                tree = javalang.parse.parse(content)

                package_name = tree.package.name if tree.package else ""

                declarations = []

                declarations.extend(
                    node
                    for _, node in tree.filter(
                        javalang.tree.ClassDeclaration
                    )
                )

                declarations.extend(
                    node
                    for _, node in tree.filter(
                        javalang.tree.InterfaceDeclaration
                    )
                )

                for declaration in declarations:
                    self.extract_module(
                        declaration,
                        rel_path,
                        package_name,
                    )

            except Exception as ex:
                print(f"[JAVA ERROR] {rel_path}: {ex}")

    def detect_module_type(self, name, annotations, declaration):
        annotation_names = {
            self.annotation_name(annotation)
            for annotation in annotations
        }

        if "RestController" in annotation_names:
            return "Controller"

        if "Controller" in annotation_names:
            return "Controller"

        if "Service" in annotation_names:
            return "Service"

        if "Repository" in annotation_names:
            return "Repository"

        if "Entity" in annotation_names:
            return "Entity"

        if "Component" in annotation_names:
            return "Component"

        if "Configuration" in annotation_names:
            return "Configuration"

        if "Mapper" in annotation_names:
            return "Mapper"

        if name.endswith("Repository"):
            return "Repository"

        if name.endswith(("Mapper", "Dao", "DAO")):
            return "Mapper"

        if "Batch" in name:
            return "Batch"

        if isinstance(
            declaration,
            javalang.tree.InterfaceDeclaration,
        ):
            return "Interface"

        return "Unknown"

    def build_summary(
        self,
        declaration,
        module_type,
        endpoints,
        method_names,
    ):
        documentation = getattr(
            declaration,
            "documentation",
            None,
        )

        if documentation:
            cleaned = re.sub(
                r"^/\*\*|\*/$",
                "",
                documentation.strip(),
            )

            lines = [
                re.sub(r"^\s*\*\s?", "", line).strip()
                for line in cleaned.splitlines()
            ]

            lines = [line for line in lines if line]

            if lines:
                return lines[0]

        if module_type == "Controller" and endpoints:
            return "Expose endpoint: " + "; ".join(endpoints)

        if method_names:
            preview = ", ".join(method_names[:5])
            return f"{module_type} class - main methods: {preview}"

        return f"{module_type} class {declaration.name}"

    def extract_module(
        self,
        declaration,
        file_path,
        package_name,
    ):
        annotations = declaration.annotations or []

        module_type = self.detect_module_type(
            declaration.name,
            annotations,
            declaration,
        )

        class_base_path = (
            self.get_class_base_path(declaration)
            if module_type == "Controller"
            else ""
        )

        field_var_types = {}
        dependencies = set()

        for field in getattr(declaration, "fields", []) or []:
            type_name = self.get_simple_type_name(
                self.type_to_str(field.type)
            )

            dependencies.add(type_name)

            for declarator in field.declarators:
                field_var_types[declarator.name] = type_name

        constructor_params = self.extract_constructor_dependencies(
            declaration
        )

        for variable_name, type_name in constructor_params.items():
            field_var_types.setdefault(variable_name, type_name)
            dependencies.add(type_name)

        method_names_in_class = {
            method.name
            for method in declaration.methods
        }

        source_methods = []
        class_tables = set()
        external_integrations = set()
        all_endpoints = []

        for method in declaration.methods:
            method_key = f"{declaration.name}.{method.name}"

            calls_internal = set()
            direct_tables = set()
            columns_by_table = defaultdict(set)

            if method.body:
                try:
                    for _, node in method:
                        if not isinstance(
                            node,
                            javalang.tree.MethodInvocation,
                        ):
                            continue

                        called_method = node.member

                        if called_method in IGNORE_METHODS:
                            continue

                        qualifier = getattr(
                            node,
                            "qualifier",
                            None,
                        )

                        called_key = None

                        if qualifier and qualifier in field_var_types:
                            dependency_type = field_var_types[qualifier]

                            called_key = (
                                f"{dependency_type}.{called_method}"
                            )

                            calls_internal.add(called_key)

                            if dependency_type.endswith(
                                EXTERNAL_CLIENT_SUFFIXES
                            ):
                                external_integrations.add(
                                    dependency_type
                                )

                        elif (
                            not qualifier
                            and called_method in method_names_in_class
                            and called_method != method.name
                        ):
                            called_key = (
                                f"{declaration.name}.{called_method}"
                            )

                            calls_internal.add(called_key)

                        if called_key:
                            self.call_graph[method_key].add(called_key)

                            self.apply_operation_impact(
                                called_key,
                                direct_tables,
                                columns_by_table,
                            )

                except Exception as ex:
                    print(
                        f"[METHOD WARNING] "
                        f"{method_key}: {ex}"
                    )

            endpoint = self.get_endpoint(
                method,
                class_base_path,
            )

            if endpoint:
                all_endpoints.append(endpoint)

            params = [
                self.type_to_str(parameter.type)
                for parameter in method.parameters
            ]

            returns = self.type_to_str(method.return_type)

            method_result = {
                "name": method.name,
                "method_key": method_key,
                "endpoint": endpoint,
                "params": params,
                "returns": returns,
                "calls_to_internal": sorted(calls_internal),
                "affected_tables": sorted(direct_tables),
                "affected_columns": {
                    table: sorted(columns)
                    for table, columns
                    in columns_by_table.items()
                },
            }

            source_methods.append(method_result)
            self.method_result_map[method_key] = method_result

            class_tables.update(direct_tables)

        related_files = set()

        for dependency in dependencies:
            dependency_file = self.class_file_map.get(dependency)

            if dependency_file:
                related_files.add(dependency_file)

        for method in source_methods:
            for call_key in method["calls_to_internal"]:
                operation = self.resolve_operation(call_key)

                if operation:
                    source_file = (
                        operation.get("mapper_path")
                        or operation.get("source_file")
                    )

                    if source_file:
                        related_files.add(source_file)

        summary = self.build_summary(
            declaration,
            module_type,
            all_endpoints,
            [method["name"] for method in source_methods],
        )

        entity_info = self.entity_metadata.get(declaration.name)

        module = {
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "package_name": package_name,
            "module_name": declaration.name,
            "module_type": module_type,
            "summary": summary,
            "source_class": declaration.name,
            "source_methods": source_methods,
            "dependencies": sorted(dependencies),
            "tables": sorted(class_tables),
            "table_details": [],
            "external_integrations": sorted(
                external_integrations
            ),
            "related_files": sorted(related_files),
        }

        if entity_info:
            module["entity_mapping"] = entity_info
            module["tables"] = [entity_info["table"]]

        self.result["modules"].append(module)
        self.module_map[declaration.name] = module

    def extract_constructor_dependencies(self, declaration):
        result = {}

        for constructor in declaration.constructors or []:
            for parameter in constructor.parameters:
                type_name = self.get_simple_type_name(
                    self.type_to_str(parameter.type)
                )

                result[parameter.name] = type_name

        return result

    def resolve_operation(self, call_key):
        if call_key in self.mapper_operation_map:
            return self.mapper_operation_map[call_key]

        if call_key in self.repository_operation_map:
            return self.repository_operation_map[call_key]

        dependency_class, _, method_name = call_key.partition(".")

        candidates = self.mapper_method_index.get(
            method_name,
            [],
        )

        exact_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("mapper_class") == dependency_class
        ]

        if len(exact_candidates) == 1:
            return exact_candidates[0]

        if len(candidates) == 1:
            return candidates[0]

        # JPA built-in methods không được khai báo trực tiếp trong interface.
        entity_class = self.repository_entity_map.get(
            dependency_class
        )

        if entity_class and entity_class in self.entity_metadata:
            entity = self.entity_metadata[entity_class]

            return {
                "repository": dependency_class,
                "method": method_name,
                "operation": self.derive_operation_from_method(
                    method_name
                ),
                "tables": [entity["table"]],
                "columns_by_table": {},
                "source_file": self.class_file_map.get(
                    dependency_class
                ),
                "entity_class": entity_class,
            }

        return None

    def apply_operation_impact(
        self,
        call_key,
        target_tables,
        target_columns,
    ):
        operation = self.resolve_operation(call_key)

        if not operation:
            return

        for table in operation.get("tables", []):
            target_tables.add(table)

        for table, columns in operation.get(
            "columns_by_table",
            {},
        ).items():
            target_columns[table].update(columns)

    # =====================================================
    # IMPACT PROPAGATION
    # =====================================================

    def propagate_table_impacts(self):
        max_iterations = 20

        for _ in range(max_iterations):
            changed = False

            for caller_key, called_keys in self.call_graph.items():
                caller_method = self.method_result_map.get(caller_key)

                if not caller_method:
                    continue

                caller_tables = set(
                    caller_method.get("affected_tables", [])
                )

                caller_columns = defaultdict(set)

                for table, columns in caller_method.get(
                    "affected_columns",
                    {},
                ).items():
                    caller_columns[table].update(columns)

                before_tables = set(caller_tables)

                before_columns = {
                    table: set(columns)
                    for table, columns in caller_columns.items()
                }

                for called_key in called_keys:
                    called_method = self.method_result_map.get(
                        called_key
                    )

                    if called_method:
                        caller_tables.update(
                            called_method.get(
                                "affected_tables",
                                [],
                            )
                        )

                        for table, columns in called_method.get(
                            "affected_columns",
                            {},
                        ).items():
                            caller_columns[table].update(columns)

                    self.apply_operation_impact(
                        called_key,
                        caller_tables,
                        caller_columns,
                    )

                caller_method["affected_tables"] = sorted(
                    caller_tables
                )

                caller_method["affected_columns"] = {
                    table: sorted(columns)
                    for table, columns in caller_columns.items()
                }

                after_columns = {
                    table: set(columns)
                    for table, columns in caller_columns.items()
                }

                if (
                    caller_tables != before_tables
                    or after_columns != before_columns
                ):
                    changed = True

            if not changed:
                break

        # Update module-level tables.
        for module in self.result["modules"]:
            module_tables = set()

            for method in module["source_methods"]:
                module_tables.update(
                    method.get("affected_tables", [])
                )

            entity_mapping = module.get("entity_mapping")

            if entity_mapping:
                module_tables.add(entity_mapping["table"])

            module["tables"] = sorted(module_tables)

    # =====================================================
    # FINAL RESULT
    # =====================================================

    def finalize_result(self):
        tables = []

        for table in self.table_metadata.values():
            table["sources"] = sorted(
                table["sources"],
                key=lambda item: (
                    item.get("type") or "",
                    item.get("file") or "",
                ),
            )

            table["entity_classes"] = sorted(
                set(table["entity_classes"])
            )

            table["mappers"] = sorted(
                set(table["mappers"])
            )

            table["columns"] = sorted(
                table["columns"],
                key=lambda column: column["name"].lower(),
            )

            tables.append(table)

        tables.sort(key=lambda table: table["name"].lower())

        self.result["database_schema"]["tables"] = tables

        table_lookup = {
            self.normalize_table_key(table["name"]): table
            for table in tables
        }

        for module in self.result["modules"]:
            details = []

            for table_name in module.get("tables", []):
                table = table_lookup.get(
                    self.normalize_table_key(table_name)
                )

                if table:
                    details.append({
                        "name": table["name"],
                        "columns": table["columns"],
                    })
                else:
                    details.append({
                        "name": table_name,
                        "columns": [],
                    })

            module["table_details"] = details

        self.result["statistics"] = {
            "total_modules": len(self.result["modules"]),
            "total_tables": len(
                self.result["database_schema"]["tables"]
            ),
            "total_mapper_operations": len(
                self.result["mapper_operations"]
            ),
            "total_jpa_entities": len(
                self.entity_metadata
            ),
            "total_repository_operations": len(
                self.repository_operation_map
            ),
        }


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python analyzer.py <project-path>")
        print("")
        print("Example:")
        print(
            r"  python analyzer.py "
            r"C:\phamtu\task-manager"
        )
        sys.exit(1)

    project_path = sys.argv[1]

    if not os.path.exists(project_path):
        print(f"Project path does not exist: {project_path}")
        sys.exit(1)

    analyzer = ProjectAnalyzer(project_path)
    analyzer.run()