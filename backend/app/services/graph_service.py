"""
Neo4j graph database service for medical knowledge graph ingestion
"""
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, Neo4jError
from app.config import settings
from app.schemas.structured_document import StructuredMedicalDocument
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GraphService:
    """Service for Neo4j graph operations"""
    
    def __init__(self):
        """Initialize Neo4j driver"""
        self.driver: Optional[Driver] = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {settings.neo4j_uri}")
        except ServiceUnavailable as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            self.driver = None
        except Exception as e:
            logger.error(f"Neo4j connection error: {str(e)}")
            self.driver = None
    
    def close(self):
        """Close Neo4j driver connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def ensure_constraints(self):
        """
        Create unique constraints on key entity IDs
        Run this once on startup
        """
        if not self.driver:
            logger.error("Cannot create constraints: No Neo4j connection")
            return False
        
        constraints = [
            "CREATE CONSTRAINT patient_id_unique IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE",
            "CREATE CONSTRAINT encounter_id_unique IF NOT EXISTS FOR (e:Encounter) REQUIRE e.encounter_id IS UNIQUE",
            "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE"
        ]
        
        try:
            with self.driver.session() as session:
                for constraint in constraints:
                    try:
                        session.run(constraint)
                        logger.info(f"Created constraint: {constraint.split()[2]}")
                    except Neo4jError as e:
                        # Constraint might already exist
                        logger.info(f"Constraint already exists or error: {str(e)}")
            
            logger.info("All Neo4j constraints ensured")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create constraints: {str(e)}")
            return False
    
    def ingest_structured_document(self, doc: StructuredMedicalDocument) -> bool:
        """
        Ingest structured medical document into Neo4j graph
        
        Creates/updates:
        - Patient node
        - Encounter node
        - Claim node
        - Hospital node
        - Condition nodes
        - All relationships
        
        Args:
            doc: Validated StructuredMedicalDocument
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            logger.error("Cannot ingest document: No Neo4j connection")
            return False
        
        try:
            with self.driver.session() as session:
                # Use a transaction to ensure atomicity
                with session.begin_transaction() as tx:
                    
                    # 1. Create/Update Patient node
                    self._create_patient(tx, doc)
                    
                    # 2. Create/Update Encounter node
                    self._create_encounter(tx, doc)
                    
                    # 3. Link Patient to Encounter
                    self._link_patient_encounter(tx, doc)
                    
                    # 4. Create/Update Hospital node and link to Encounter
                    self._create_hospital(tx, doc)
                    
                    # 5. Create/Update Claim node
                    self._create_claim(tx, doc)
                    
                    # 6. Link Encounter to Claim
                    self._link_encounter_claim(tx, doc)
                    
                    # 7. Link Patient to Claim
                    self._link_patient_claim(tx, doc)
                    
                    # 8. Create Condition nodes and link to Encounter
                    self._create_conditions(tx, doc)
                    
                    # Commit transaction
                    tx.commit()
            
            logger.info(f"Successfully ingested document into Neo4j graph "
                       f"(patient: {doc.patient.patient_id}, encounter: {doc.encounter.encounter_id})")
            return True
            
        except Neo4jError as e:
            logger.error(f"Neo4j error during ingestion: {str(e)}")
            return False
        except Exception as e:
            logger.exception(f"Failed to ingest document: {str(e)}")
            return False
    
    def _create_patient(self, tx, doc: StructuredMedicalDocument):
        """Create or update Patient node"""
        query = """
        MERGE (p:Patient {patient_id: $patient_id})
        ON CREATE SET
            p.name = $name,
            p.dob = $dob,
            p.gender = $gender,
            p.insurance_policy_id = $insurance_policy_id,
            p.created_at = datetime()
        ON MATCH SET
            p.name = COALESCE($name, p.name),
            p.dob = COALESCE($dob, p.dob),
            p.gender = COALESCE($gender, p.gender),
            p.insurance_policy_id = COALESCE($insurance_policy_id, p.insurance_policy_id),
            p.updated_at = datetime()
        """
        
        tx.run(query,
               patient_id=doc.patient.patient_id,
               name=doc.patient.name,
               dob=str(doc.patient.dob) if doc.patient.dob else None,
               gender=doc.patient.gender,
               insurance_policy_id=doc.patient.insurance_policy_id)
    
    def _create_encounter(self, tx, doc: StructuredMedicalDocument):
        """Create or update Encounter node"""
        query = """
        MERGE (e:Encounter {encounter_id: $encounter_id})
        SET
            e.admission_date = $admission_date,
            e.discharge_date = $discharge_date,
            e.visit_type = $visit_type,
            e.department = $department,
            e.updated_at = datetime()
        """
        
        tx.run(query,
               encounter_id=doc.encounter.encounter_id,
               admission_date=str(doc.encounter.admission_date) if doc.encounter.admission_date else None,
               discharge_date=str(doc.encounter.discharge_date) if doc.encounter.discharge_date else None,
               visit_type=doc.encounter.visit_type,
               department=doc.encounter.department)
    
    def _link_patient_encounter(self, tx, doc: StructuredMedicalDocument):
        """Link Patient to Encounter"""
        query = """
        MATCH (p:Patient {patient_id: $patient_id})
        MATCH (e:Encounter {encounter_id: $encounter_id})
        MERGE (p)-[:HAD_ENCOUNTER]->(e)
        """
        
        tx.run(query,
               patient_id=doc.patient.patient_id,
               encounter_id=doc.encounter.encounter_id)
    
    def _create_hospital(self, tx, doc: StructuredMedicalDocument):
        """Create or update Hospital node and link to Encounter"""
        if not doc.hospital.name:
            return  # Skip if no hospital name
        
        query = """
        MERGE (h:Hospital {name: $name})
        SET
            h.hospital_id = COALESCE($hospital_id, h.hospital_id),
            h.city = COALESCE($city, h.city),
            h.updated_at = datetime()
        WITH h
        MATCH (e:Encounter {encounter_id: $encounter_id})
        MERGE (e)-[:AT_HOSPITAL]->(h)
        """
        
        tx.run(query,
               name=doc.hospital.name,
               hospital_id=doc.hospital.hospital_id,
               city=doc.hospital.city,
               encounter_id=doc.encounter.encounter_id)
    
    def _create_claim(self, tx, doc: StructuredMedicalDocument):
        """Create or update Claim node"""
        query = """
        MERGE (c:Claim {claim_id: $claim_id})
        SET
            c.claim_amount = $claim_amount,
            c.approved_amount = $approved_amount,
            c.status = $status,
            c.insurer_name = $insurer_name,
            c.submission_date = $submission_date,
            c.updated_at = datetime()
        """
        
        tx.run(query,
               claim_id=doc.claim.claim_id,
               claim_amount=doc.claim.claim_amount,
               approved_amount=doc.claim.approved_amount,
               status=doc.claim.status,
               insurer_name=doc.claim.insurer_name,
               submission_date=str(doc.claim.submission_date) if doc.claim.submission_date else None)
    
    def _link_encounter_claim(self, tx, doc: StructuredMedicalDocument):
        """Link Encounter to Claim"""
        query = """
        MATCH (e:Encounter {encounter_id: $encounter_id})
        MATCH (c:Claim {claim_id: $claim_id})
        MERGE (e)-[:GENERATED_CLAIM]->(c)
        """
        
        tx.run(query,
               encounter_id=doc.encounter.encounter_id,
               claim_id=doc.claim.claim_id)
    
    def _link_patient_claim(self, tx, doc: StructuredMedicalDocument):
        """Link Patient to Claim"""
        query = """
        MATCH (p:Patient {patient_id: $patient_id})
        MATCH (c:Claim {claim_id: $claim_id})
        MERGE (p)-[:FILED]->(c)
        """
        
        tx.run(query,
               patient_id=doc.patient.patient_id,
               claim_id=doc.claim.claim_id)
    
    def _create_conditions(self, tx, doc: StructuredMedicalDocument):
        """Create Condition nodes and link to Encounter"""
        if not doc.conditions:
            return  # No conditions to process
        
        for condition in doc.conditions:
            query = """
            MERGE (cond:Condition {condition_name: $condition_name})
            SET
                cond.icd_code = COALESCE($icd_code, cond.icd_code),
                cond.chronic = COALESCE($chronic, cond.chronic),
                cond.updated_at = datetime()
            WITH cond
            MATCH (e:Encounter {encounter_id: $encounter_id})
            MERGE (e)-[:DIAGNOSED_WITH]->(cond)
            """
            
            tx.run(query,
                   condition_name=condition.condition_name,
                   icd_code=condition.icd_code,
                   chronic=condition.chronic,
                   encounter_id=doc.encounter.encounter_id)


# Global graph service instance
graph_service = GraphService()
