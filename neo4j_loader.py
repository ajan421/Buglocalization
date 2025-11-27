"""
Neo4j Knowledge Graph Loader
Creates a knowledge graph from parsed Java code in Neo4j
"""

from neo4j import GraphDatabase
import json
from typing import Dict, List
import os


class Neo4jKnowledgeGraph:
    """Build and query knowledge graph in Neo4j"""
    
    def __init__(self, uri: str = "neo4j://127.0.0.1:7687", 
                 user: str = "neo4j", 
                 password: str = "password"):
        """Initialize Neo4j connection"""
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.verify_connectivity()
            print("✓ Connected to Neo4j")
        except Exception as e:
            print(f"✗ Could not connect to Neo4j: {e}")
            print("\nTo start Neo4j:")
            print("1. Download Neo4j Desktop: https://neo4j.com/download/")
            print("2. Create a database with password 'password'")
            print("3. Start the database")
            self.driver = None
    
    def verify_connectivity(self):
        """Verify Neo4j connection"""
        with self.driver.session() as session:
            result = session.run("RETURN 1")
            result.single()
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
    
    def clear_database(self):
        """Clear all nodes and relationships"""
        if not self.driver:
            return
        
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("✓ Cleared database")
    
    def create_indexes(self):
        """Create indexes for better query performance"""
        if not self.driver:
            return
        
        with self.driver.session() as session:
            # Create indexes
            session.run("CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.full_name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (m:Method) ON (m.signature)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (f:Field) ON (f.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (p:Package) ON (p.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (file:File) ON (file.path)")
            print("✓ Created indexes")
    
    def load_parsed_data(self, parsed_data: Dict):
        """Load parsed code data into Neo4j"""
        if not self.driver:
            print("✗ No Neo4j connection available")
            return
        
        with self.driver.session() as session:
            # Create file nodes
            for file_info in parsed_data['files']:
                self._create_file_node(session, file_info)
                
                # Create package node
                if file_info['package']:
                    self._create_package_node(session, file_info['package'])
                
                # Create class nodes
                for cls_info in file_info['classes']:
                    self._create_class_node(session, cls_info)
                    
                    # Create method nodes
                    for method_info in cls_info['methods']:
                        self._create_method_node(session, method_info)
                    
                    # Create field nodes
                    for field_info in cls_info['fields']:
                        self._create_field_node(session, field_info)
        
        print(f"✓ Loaded {parsed_data['total_classes']} classes, "
              f"{parsed_data['total_methods']} methods, "
              f"{parsed_data['total_fields']} fields into Neo4j")
    
    def _create_file_node(self, session, file_info: Dict):
        """Create a file node"""
        session.run("""
            MERGE (f:File {path: $path})
            SET f.package = $package
        """, path=file_info['file_path'], package=file_info['package'])
    
    def _create_package_node(self, session, package_name: str):
        """Create a package node"""
        session.run("""
            MERGE (p:Package {name: $name})
        """, name=package_name)
    
    def _create_class_node(self, session, cls_info: Dict):
        """Create a class node with relationships"""
        # Create class node
        session.run("""
            MERGE (c:Class {full_name: $full_name})
            SET c.name = $name,
                c.type = $type,
                c.package = $package,
                c.file_path = $file_path,
                c.modifiers = $modifiers,
                c.javadoc = $javadoc
        """, 
            full_name=cls_info['full_name'],
            name=cls_info['name'],
            type=cls_info['type'],
            package=cls_info['package'],
            file_path=cls_info['file_path'],
            modifiers=cls_info['modifiers'],
            javadoc=cls_info.get('javadoc', '')
        )
        
        # Link to file
        session.run("""
            MATCH (c:Class {full_name: $full_name})
            MATCH (f:File {path: $file_path})
            MERGE (c)-[:DEFINED_IN]->(f)
        """, full_name=cls_info['full_name'], file_path=cls_info['file_path'])
        
        # Link to package
        if cls_info['package']:
            session.run("""
                MATCH (c:Class {full_name: $full_name})
                MATCH (p:Package {name: $package})
                MERGE (c)-[:BELONGS_TO]->(p)
            """, full_name=cls_info['full_name'], package=cls_info['package'])
        
        # Create inheritance relationship
        if cls_info.get('extends'):
            parent_full_name = f"{cls_info['package']}.{cls_info['extends']}" if '.' not in cls_info['extends'] else cls_info['extends']
            session.run("""
                MATCH (c:Class {full_name: $full_name})
                MERGE (parent:Class {full_name: $parent_full_name})
                MERGE (c)-[:EXTENDS]->(parent)
            """, full_name=cls_info['full_name'], parent_full_name=parent_full_name)
        
        # Create implementation relationships
        for interface in cls_info.get('implements', []):
            interface_full_name = f"{cls_info['package']}.{interface}" if '.' not in interface else interface
            session.run("""
                MATCH (c:Class {full_name: $full_name})
                MERGE (i:Class {full_name: $interface_full_name})
                MERGE (c)-[:IMPLEMENTS]->(i)
            """, full_name=cls_info['full_name'], interface_full_name=interface_full_name)
    
    def _create_method_node(self, session, method_info: Dict):
        """Create a method node"""
        signature = self._create_method_signature(method_info)
        param_types = [p['type'] for p in method_info['parameters']]
        
        session.run("""
            MERGE (m:Method {signature: $signature})
            SET m.name = $name,
                m.return_type = $return_type,
                m.class = $class_name,
                m.modifiers = $modifiers,
                m.param_types = $param_types,
                m.javadoc = $javadoc
        """,
            signature=signature,
            name=method_info['name'],
            return_type=method_info['return_type'],
            class_name=method_info['class'],
            modifiers=method_info['modifiers'],
            param_types=param_types,
            javadoc=method_info.get('javadoc', '')
        )
        
        # Link to class
        session.run("""
            MATCH (m:Method {signature: $signature})
            MATCH (c:Class {full_name: $class_name})
            MERGE (c)-[:HAS_METHOD]->(m)
        """, signature=signature, class_name=method_info['class'])
    
    def _create_field_node(self, session, field_info: Dict):
        """Create a field node"""
        field_id = f"{field_info['class']}.{field_info['name']}"
        
        session.run("""
            MERGE (f:Field {id: $id})
            SET f.name = $name,
                f.type = $type,
                f.class = $class_name,
                f.modifiers = $modifiers
        """,
            id=field_id,
            name=field_info['name'],
            type=field_info['type'],
            class_name=field_info['class'],
            modifiers=field_info['modifiers']
        )
        
        # Link to class
        session.run("""
            MATCH (f:Field {id: $id})
            MATCH (c:Class {full_name: $class_name})
            MERGE (c)-[:HAS_FIELD]->(f)
        """, id=field_id, class_name=field_info['class'])
    
    def _create_method_signature(self, method_info: Dict) -> str:
        """Create unique method signature"""
        params = ', '.join([p['type'] for p in method_info['parameters']])
        return f"{method_info['class']}.{method_info['name']}({params})"
    
    def query_classes_by_name(self, class_name: str) -> List[Dict]:
        """Search for classes by name"""
        if not self.driver:
            return []
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Class)
                WHERE c.name CONTAINS $class_name
                RETURN c.full_name as full_name, c.name as name, 
                       c.file_path as file_path, c.javadoc as javadoc
                LIMIT 10
            """, class_name=class_name)
            
            return [dict(record) for record in result]
    
    def query_methods_by_name(self, method_name: str) -> List[Dict]:
        """Search for methods by name"""
        if not self.driver:
            return []
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
                WHERE m.name CONTAINS $method_name
                RETURN m.signature as signature, m.name as name,
                       m.return_type as return_type, c.full_name as class_name,
                       c.file_path as file_path
                LIMIT 10
            """, method_name=method_name)
            
            return [dict(record) for record in result]
    
    def query_related_classes(self, class_name: str) -> List[Dict]:
        """Find classes related to a given class"""
        if not self.driver:
            return []
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Class {full_name: $class_name})
                OPTIONAL MATCH (c)-[r:EXTENDS|IMPLEMENTS]-(related:Class)
                RETURN DISTINCT related.full_name as full_name, 
                       related.name as name, type(r) as relationship
                LIMIT 20
            """, class_name=class_name)
            
            return [dict(record) for record in result]


if __name__ == "__main__":
    # Example usage
    kg = Neo4jKnowledgeGraph()
    
    if kg.driver:
        # Load parsed data
        if os.path.exists('parsed_code.json'):
            with open('parsed_code.json', 'r') as f:
                parsed_data = json.load(f)
            
            print("\nClearing database...")
            kg.clear_database()
            
            print("\nCreating indexes...")
            kg.create_indexes()
            
            print("\nLoading data into Neo4j...")
            kg.load_parsed_data(parsed_data)
            
            print("\n✓ Knowledge graph created successfully!")
        else:
            print("✗ parsed_code.json not found. Run code_parser.py first.")
    
    kg.close()

