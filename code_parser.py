"""
Code Parser for AspectJ Weaver Module
Extracts classes, methods, fields, and their relationships from Java source files
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set
import javalang


class CodeParser:
    """Parse Java source code and extract structured information"""
    
    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.classes = []
        self.methods = []
        self.fields = []
        self.relationships = []
        
    def parse_java_file(self, file_path: Path) -> Dict:
        """Parse a single Java file and extract information"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse using javalang
            try:
                tree = javalang.parse.parse(content)
            except Exception as parse_error:
                print(f"Warning: Could not parse {file_path}: {parse_error}")
                return self._fallback_parse(file_path, content)
            
            file_info = {
                'file_path': str(file_path.relative_to(self.source_dir)),
                'package': tree.package.name if tree.package else '',
                'imports': [imp.path for imp in tree.imports] if tree.imports else [],
                'classes': []
            }
            
            # Extract classes
            for path, node in tree.filter(javalang.tree.ClassDeclaration):
                class_info = self._extract_class_info(node, file_info['package'], file_path, content)
                file_info['classes'].append(class_info)
                
            # Extract interfaces
            for path, node in tree.filter(javalang.tree.InterfaceDeclaration):
                class_info = self._extract_interface_info(node, file_info['package'], file_path, content)
                file_info['classes'].append(class_info)
            
            return file_info
            
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None
    
    def _fallback_parse(self, file_path: Path, content: str) -> Dict:
        """Fallback parser using regex when javalang fails"""
        file_info = {
            'file_path': str(file_path.relative_to(self.source_dir)),
            'package': '',
            'imports': [],
            'classes': []
        }
        
        # Extract package
        package_match = re.search(r'package\s+([\w.]+);', content)
        if package_match:
            file_info['package'] = package_match.group(1)
        
        # Extract imports
        imports = re.findall(r'import\s+([\w.]+);', content)
        file_info['imports'] = imports
        
        # Extract class names (simple regex)
        class_matches = re.finditer(
            r'(public|private|protected)?\s*(abstract|final)?\s*(class|interface)\s+(\w+)',
            content
        )
        for match in class_matches:
            class_name = match.group(4)
            file_info['classes'].append({
                'name': class_name,
                'type': match.group(3),
                'package': file_info['package'],
                'file_path': str(file_path.relative_to(self.source_dir)),
                'methods': [],
                'fields': []
            })
        
        return file_info
    
    def _extract_class_info(self, node, package: str, file_path: Path, content: str) -> Dict:
        """Extract information about a class"""
        class_info = {
            'name': node.name,
            'type': 'class',
            'package': package,
            'full_name': f"{package}.{node.name}" if package else node.name,
            'file_path': str(file_path.relative_to(self.source_dir)),
            'modifiers': list(node.modifiers) if node.modifiers else [],
            'extends': node.extends.name if node.extends else None,
            'implements': [impl.name for impl in node.implements] if node.implements else [],
            'methods': [],
            'fields': [],
            'javadoc': node.documentation if hasattr(node, 'documentation') else None
        }
        
        # Extract methods
        for method in node.methods if node.methods else []:
            method_info = self._extract_method_info(method, class_info['full_name'])
            class_info['methods'].append(method_info)
        
        # Extract fields
        for field_decl in node.fields if node.fields else []:
            for declarator in field_decl.declarators:
                field_info = {
                    'name': declarator.name,
                    'type': field_decl.type.name if hasattr(field_decl.type, 'name') else str(field_decl.type),
                    'modifiers': list(field_decl.modifiers) if field_decl.modifiers else [],
                    'class': class_info['full_name']
                }
                class_info['fields'].append(field_info)
        
        return class_info
    
    def _extract_interface_info(self, node, package: str, file_path: Path, content: str) -> Dict:
        """Extract information about an interface"""
        interface_info = {
            'name': node.name,
            'type': 'interface',
            'package': package,
            'full_name': f"{package}.{node.name}" if package else node.name,
            'file_path': str(file_path.relative_to(self.source_dir)),
            'modifiers': list(node.modifiers) if node.modifiers else [],
            'extends': [ext.name for ext in node.extends] if node.extends else [],
            'methods': [],
            'fields': [],
            'javadoc': node.documentation if hasattr(node, 'documentation') else None
        }
        
        # Extract methods
        for method in node.methods if node.methods else []:
            method_info = self._extract_method_info(method, interface_info['full_name'])
            interface_info['methods'].append(method_info)
        
        return interface_info
    
    def _extract_method_info(self, method, class_full_name: str) -> Dict:
        """Extract information about a method"""
        return_type = 'void'
        if method.return_type:
            if hasattr(method.return_type, 'name'):
                return_type = method.return_type.name
            else:
                return_type = str(method.return_type)
        
        parameters = []
        if method.parameters:
            for param in method.parameters:
                param_type = param.type.name if hasattr(param.type, 'name') else str(param.type)
                parameters.append({
                    'name': param.name,
                    'type': param_type
                })
        
        return {
            'name': method.name,
            'return_type': return_type,
            'parameters': parameters,
            'modifiers': list(method.modifiers) if method.modifiers else [],
            'class': class_full_name,
            'javadoc': method.documentation if hasattr(method, 'documentation') else None
        }
    
    def parse_directory(self, max_files: int = None) -> Dict:
        """Parse all Java files in the directory"""
        java_files = list(self.source_dir.rglob('*.java'))
        
        if max_files:
            java_files = java_files[:max_files]
        
        print(f"Found {len(java_files)} Java files to parse")
        
        parsed_data = {
            'files': [],
            'total_classes': 0,
            'total_methods': 0,
            'total_fields': 0
        }
        
        for i, java_file in enumerate(java_files):
            if i % 10 == 0:
                print(f"Parsing file {i+1}/{len(java_files)}: {java_file.name}")
            
            file_info = self.parse_java_file(java_file)
            if file_info:
                parsed_data['files'].append(file_info)
                for cls in file_info['classes']:
                    parsed_data['total_classes'] += 1
                    parsed_data['total_methods'] += len(cls['methods'])
                    parsed_data['total_fields'] += len(cls['fields'])
        
        print(f"\nParsing complete!")
        print(f"Total classes: {parsed_data['total_classes']}")
        print(f"Total methods: {parsed_data['total_methods']}")
        print(f"Total fields: {parsed_data['total_fields']}")
        
        return parsed_data


if __name__ == "__main__":
    # Example usage
    parser = CodeParser("aspectj/weaver/src")
    parsed_data = parser.parse_directory()
    
    # Save to JSON for inspection
    import json
    with open('parsed_code.json', 'w') as f:
        json.dump(parsed_data, f, indent=2)
    print("\nSaved parsed data to parsed_code.json")

