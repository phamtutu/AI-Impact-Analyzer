import os
import re
import json
import javalang
from pathlib import Path

IGNORE_METHODS = {
    "info",
    "warn",
    "error",
    "debug",
    "trace",
    "equals",
    "hashCode",
    "toString",
    "add",
    "remove",
    "contains",
    "stream",
    "collect",
    "filter",
    "map",
    "forEach"
}


class ProjectAnalyzer:

    def __init__(self, project_path):

        self.project_path = project_path

        self.result = {
            "project": {
                "name": Path(project_path).name
            },
            "database": {
                "db_type": "UNKNOWN"
            },
            "modules": [],
            "mapper_operations": []
        }

        self.mapper_table_map = {}
        self.global_tables = set()

    # =====================================================
    # RUN
    # =====================================================

    def run(self):

        self.detect_database()

        self.scan_mapper_xml()

        self.scan_java()

        with open(
            "project-knowledge.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.result,
                f,
                ensure_ascii=False,
                indent=2
            )

        print("DONE -> project-knowledge.json")

    # =====================================================
    # DATABASE
    # =====================================================

    def detect_database(self):

        for root, _, files in os.walk(self.project_path):

            for file in files:

                if file not in [
                    "application.yml",
                    "application.yaml",
                    "application.properties"
                ]:
                    continue

                path = os.path.join(root, file)

                try:

                    content = open(
                        path,
                        encoding="utf-8",
                        errors="ignore"
                    ).read().lower()

                    if "postgresql" in content:
                        self.result["database"]["db_type"] = "PostgreSQL"

                    elif "oracle" in content:
                        self.result["database"]["db_type"] = "Oracle"

                    elif "mysql" in content:
                        self.result["database"]["db_type"] = "MySQL"

                    elif "mariadb" in content:
                        self.result["database"]["db_type"] = "MariaDB"

                except:
                    pass

    # =====================================================
    # MAPPER XML
    # =====================================================

    def scan_mapper_xml(self):

        tags = {
            "select": "SELECT",
            "insert": "INSERT",
            "update": "UPDATE",
            "delete": "DELETE"
        }

        for root, _, files in os.walk(self.project_path):

            for file in files:

                if not file.endswith(".xml"):
                    continue

                full_path = os.path.join(root, file)

                try:

                    content = open(
                        full_path,
                        encoding="utf-8",
                        errors="ignore"
                    ).read()

                    for tag, operation in tags.items():

                        pattern = (
                            rf'<{tag}.*?id="([^"]+)".*?>'
                            rf'(.*?)'
                            rf'</{tag}>'
                        )

                        matches = re.findall(
                            pattern,
                            content,
                            re.I | re.S
                        )

                        for method_id, sql in matches:

                            tables = set()

                            for regex in [

                                r'FROM\s+([A-Z0-9_]+)',

                                r'JOIN\s+([A-Z0-9_]+)',

                                r'UPDATE\s+([A-Z0-9_]+)',

                                r'INTO\s+([A-Z0-9_]+)'
                            ]:

                                found = re.findall(
                                    regex,
                                    sql,
                                    re.I
                                )

                                tables.update(found)

                            table_list = sorted(
                                list(tables)
                            )

                            self.result[
                                "mapper_operations"
                            ].append({
                                "mapper": file,
                                "method": method_id,
                                "operation": operation,
                                "tables": table_list
                            })

                            self.mapper_table_map[
                                method_id
                            ] = table_list

                            self.global_tables.update(
                                table_list
                            )

                except Exception as ex:
                    print(
                        f"[XML ERROR] {full_path}"
                    )
                    print(ex)

    # =====================================================
    # JAVA
    # =====================================================

    def scan_java(self):

        for root, _, files in os.walk(
            self.project_path
        ):

            for file in files:

                if not file.endswith(".java"):
                    continue

                full_path = os.path.join(
                    root,
                    file
                )

                try:
                    self.parse_java(
                        full_path
                    )

                except Exception as ex:

                    print(
                        f"[JAVA ERROR] {full_path}"
                    )

                    print(ex)

    def parse_java(self, file_path):

        content = open(
            file_path,
            encoding="utf-8",
            errors="ignore"
        ).read()

        tree = javalang.parse.parse(
            content
        )

        package_name = ""

        if tree.package:
            package_name = tree.package.name

        for _, cls in tree.filter(
            javalang.tree.ClassDeclaration
        ):

            self.extract_module(
                cls,
                file_path,
                package_name
            )

    # =====================================================
    # MODULE TYPE
    # =====================================================

    def detect_module_type(
        self,
        cls_name,
        annotations
    ):

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
    # MODULE
    # =====================================================

    def extract_module(
        self,
        cls,
        file_path,
        package_name
    ):

        annotations = [
            a.name
            for a in cls.annotations
        ]

        module_type = self.detect_module_type(
            cls.name,
            annotations
        )

        dependencies = []

        for field in cls.fields:

            try:

                dependencies.append(
                    field.type.name
                )

            except:
                pass

        dependencies = sorted(
            list(set(dependencies))
        )

        source_methods = []

        table_set = set()

        for method in cls.methods:

            calls = []

            try:

                for _, node in method:

                    if not isinstance(
                        node,
                        javalang.tree.MethodInvocation
                    ):
                        continue

                    method_name = node.member

                    if (
                        method_name
                        in IGNORE_METHODS
                    ):
                        continue

                    if method_name.startswith(
                        "get"
                    ):
                        continue

                    if method_name.startswith(
                        "set"
                    ):
                        continue

                    qualifier = getattr(
                        node,
                        "qualifier",
                        None
                    )

                    if qualifier:

                        call_name = (
                            f"{qualifier}.{method_name}"
                        )

                    else:

                        call_name = method_name

                    calls.append(call_name)

                    if (
                        method_name
                        in self.mapper_table_map
                    ):

                        table_set.update(
                            self.mapper_table_map[
                                method_name
                            ]
                        )

            except:
                pass

            source_methods.append({
                "name": method.name,
                "calls_to": sorted(
                    list(set(calls))
                )
            })

        module = {

            "file_name":
                os.path.basename(
                    file_path
                ),

            "file_path":
                file_path,

            "module_name":
                cls.name,

            "module_type":
                module_type,

            "package":
                package_name,

            "source_class":
                cls.name,

            "source_methods":
                source_methods,

            "dependencies":
                dependencies,

            "tables":
                sorted(
                    list(table_set)
                )
        }

        self.result["modules"].append(
            module
        )


if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print(
            "Usage: python analyzer.py <project-path>"
        )

        exit()

    analyzer = ProjectAnalyzer(
        sys.argv[1]
    )

    analyzer.run()