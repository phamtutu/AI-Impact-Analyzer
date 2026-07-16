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
    "forEach",
    "now"
}


class SpringAnalyzer:

    def __init__(self, source_root):

        self.source_root = source_root

        self.result = {
            "project": {
                "name": Path(source_root).name
            },
            "modules": [],
            "mapper_operations": [],
            "tables": [],
            "dependencies": []
        }

        self.tables = set()
        self.dependencies = []

    def run(self):

        self.scan_java()

        self.scan_mapper_xml()

        self.result["tables"] = sorted(
            list(self.tables)
        )

        self.result["dependencies"] = self.dependencies

        with open(
            "project-knowledge.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.result,
                f,
                indent=2,
                ensure_ascii=False
            )

        print(
            "Created: project-knowledge.json"
        )

    def scan_java(self):

        for root, _, files in os.walk(
            self.source_root
        ):

            for file in files:

                if not file.endswith(".java"):
                    continue

                full_path = os.path.join(
                    root,
                    file
                )

                try:
                    self.parse_java_file(
                        full_path
                    )
                except Exception as ex:
                    print(
                        "ERROR:",
                        full_path,
                        ex
                    )

    def parse_java_file(
        self,
        file_path
    ):

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
            package_name = (
                tree.package.name
            )

        for _, cls in tree.filter(
            javalang.tree.ClassDeclaration
        ):

            self.extract_class(
                cls,
                content,
                package_name,
                file_path
            )

    def extract_class(
        self,
        cls,
        content,
        package_name,
        file_path
    ):

        annotations = [
            a.name
            for a in cls.annotations
        ]

        module_type = "Unknown"

        if "RestController" in annotations:
            module_type = "Controller"

        elif "Service" in annotations:
            module_type = "Service"

        elif "Entity" in annotations:
            module_type = "Entity"

        elif "Component" in annotations:
            module_type = "Component"

        elif "Repository" in annotations:
            module_type = "Repository"

        dependencies = {
            "services": [],
            "repositories": [],
            "mappers": [],
            "others": []
        }

        for field in cls.fields:

            try:

                field_type = field.type.name

                if field_type.endswith(
                    "Service"
                ):
                    dependencies[
                        "services"
                    ].append(
                        field_type
                    )

                elif field_type.endswith(
                    "Repository"
                ):
                    dependencies[
                        "repositories"
                    ].append(
                        field_type
                    )

                elif field_type.endswith(
                    "Mapper"
                ):
                    dependencies[
                        "mappers"
                    ].append(
                        field_type
                    )

                else:
                    dependencies[
                        "others"
                    ].append(
                        field_type
                    )

            except:
                pass

        important_calls = set()

        methods = []

        transactional_methods = []

        for method in cls.methods:

            methods.append(
                method.name
            )

            annotations = [
                a.name
                for a in method.annotations
            ]

            if (
                "Transactional"
                in annotations
            ):
                transactional_methods.append(
                    method.name
                )

            try:

                for _, node in method:

                    if not isinstance(
                        node,
                        javalang.tree.MethodInvocation
                    ):
                        continue

                    method_name = (
                        node.member
                    )

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

                    important_calls.add(
                        method_name
                    )

            except:
                pass

        table_name = None

        if "Entity" in annotations:

            m = re.search(
                r'@Table\s*\(\s*name\s*=\s*"([^"]+)"',
                content
            )

            if m:
                table_name = (
                    m.group(1)
                )
            else:
                table_name = cls.name

            self.tables.add(
                table_name
            )

        external_integrations = []

        for svc in dependencies[
            "services"
        ]:

            if any(
                k in svc.lower()
                for k in [
                    "gateway",
                    "client",
                    "notification",
                    "api",
                    "provision"
                ]
            ):
                external_integrations.append(
                    svc
                )

        complexity_score = (
            len(
                dependencies[
                    "services"
                ]
            ) * 2
            + len(
                dependencies[
                    "mappers"
                ]
            ) * 2
            + len(
                external_integrations
            ) * 3
            + len(
                transactional_methods
            ) * 3
        )

        module = {
            "filename":
                os.path.basename(
                    file_path
                ),

            "module_name":
                cls.name,

            "module_type":
                module_type,

            "package":
                package_name,

            "methods":
                methods,

            "dependencies":
                dependencies,

            "external_integrations":
                external_integrations,

            "important_calls":
                sorted(
                    list(
                        important_calls
                    )
                ),

            "transactional_methods":
                transactional_methods,

            "complexity": {
                "score":
                    complexity_score
            }
        }

        self.result[
            "modules"
        ].append(module)

        for dep_type in (
            dependencies
        ):

            for dep in (
                dependencies[
                    dep_type
                ]
            ):

                self.dependencies.append(
                    {
                        "from":
                            cls.name,

                        "to":
                            dep
                    }
                )

    def scan_mapper_xml(self):

        for root, _, files in os.walk(
            self.source_root
        ):

            for file in files:

                if not file.endswith(
                    ".xml"
                ):
                    continue

                full_path = os.path.join(
                    root,
                    file
                )

                try:

                    content = open(
                        full_path,
                        encoding="utf-8",
                        errors="ignore"
                    ).read()

                    self.extract_mapper(
                        file,
                        content
                    )

                except:
                    pass

    def extract_mapper(
        self,
        mapper_name,
        content
    ):

        tags = {
            "select": "SELECT",
            "insert": "INSERT",
            "update": "UPDATE",
            "delete": "DELETE"
        }

        for tag, op in tags.items():

            pattern = (
                rf"<{tag}.*?id=\"([^\"]+)\".*?>"
                rf"(.*?)"
                rf"</{tag}>"
            )

            matches = re.findall(
                pattern,
                content,
                re.S | re.I
            )

            for (
                method_id,
                sql
            ) in matches:

                tables = set()

                table_patterns = [
                    r'FROM\s+([A-Z0-9_]+)',
                    r'JOIN\s+([A-Z0-9_]+)',
                    r'UPDATE\s+([A-Z0-9_]+)',
                    r'INTO\s+([A-Z0-9_]+)'
                ]

                for p in (
                    table_patterns
                ):

                    found = re.findall(
                        p,
                        sql,
                        re.I
                    )

                    tables.update(
                        found
                    )

                for t in tables:
                    self.tables.add(t)

                self.result[
                    "mapper_operations"
                ].append(
                    {
                        "mapper":
                            mapper_name,

                        "method":
                            method_id,

                        "operation":
                            op,

                        "tables":
                            list(
                                tables
                            )
                    }
                )


if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "python analyzer.py <source_path>"
        )

        exit()

    SpringAnalyzer(
        sys.argv[1]
    ).run()