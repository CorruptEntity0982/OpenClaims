"""
LLM service for structured medical information extraction using AWS Bedrock
"""
import boto3
import json
from botocore.exceptions import ClientError
from app.config import settings
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """Service for AWS Bedrock LLM operations"""
    
    def __init__(self):
        """Initialize Bedrock Runtime client"""
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    def extract_structured_data(self, raw_text: str) -> Optional[Dict]:
        """
        Extract structured medical information from raw text using Claude
        
        Args:
            raw_text: Raw text extracted from medical document
            
        Returns:
            Dictionary containing structured medical data, or None if extraction fails
        """
        try:
            logger.info("Starting LLM structured extraction")
            
            # Construct the extraction prompt
            prompt = self._build_extraction_prompt(raw_text)
            
            # Call Bedrock with Claude
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "temperature": 0,  # Deterministic output
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            extracted_text = response_body['content'][0]['text']
            
            logger.info(f"LLM extraction completed. Response length: {len(extracted_text)} chars")
            
            # Parse JSON from response
            # Claude might wrap JSON in markdown code blocks, so clean it
            json_text = self._extract_json_from_response(extracted_text)
            structured_data = json.loads(json_text)
            
            logger.info("Successfully parsed structured data from LLM response")
            return structured_data
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = f"Bedrock ClientError ({error_code}): {str(e)}"
            logger.error(error_msg)
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"Raw response: {extracted_text[:500] if 'extracted_text' in locals() else 'N/A'}")
            return None
            
        except Exception as e:
            error_msg = f"LLM extraction failed: {str(e)}"
            logger.error(error_msg)
            return None
    
    def _build_extraction_prompt(self, raw_text: str) -> str:
        """
        Build the extraction prompt with strict instructions
        
        Args:
            raw_text: Raw text from document
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are a medical information extraction system. Extract structured data from the following medical document text.

STRICT RULES:
1. Return ONLY valid JSON, no commentary, no markdown formatting
2. Extract only the fields defined in the schema below
3. If a field is missing from the document, use null
4. Do NOT hallucinate or infer ICD codes - only include if explicitly stated
5. Do NOT assume chronic conditions - only mark chronic: true if explicitly stated
6. All dates MUST be in ISO format YYYY-MM-DD
7. All IDs (patient_id, encounter_id, claim_id) are REQUIRED - if missing, try to infer from document numbers/codes
8. If you cannot find required IDs, generate them in format: PATIENT_XXX, ENCOUNTER_XXX, CLAIM_XXX where XXX is derived from document

REQUIRED JSON SCHEMA:
{{
  "patient": {{
    "patient_id": "string (REQUIRED)",
    "name": "string or null",
    "dob": "YYYY-MM-DD or null",
    "gender": "M/F/Other or null",
    "insurance_policy_id": "string or null"
  }},
  "encounter": {{
    "encounter_id": "string (REQUIRED)",
    "admission_date": "YYYY-MM-DD or null",
    "discharge_date": "YYYY-MM-DD or null",
    "visit_type": "inpatient/outpatient/emergency or null",
    "department": "string or null"
  }},
  "claim": {{
    "claim_id": "string (REQUIRED)",
    "claim_amount": number or null,
    "approved_amount": number or null,
    "status": "submitted/approved/rejected/pending or null",
    "insurer_name": "string or null",
    "submission_date": "YYYY-MM-DD or null"
  }},
  "conditions": [
    {{
      "condition_name": "string (REQUIRED)",
      "icd_code": "string or null (only if explicitly stated)",
      "chronic": boolean or null (only true if explicitly stated as chronic)
    }}
  ],
  "hospital": {{
    "hospital_id": "string or null",
    "name": "string or null",
    "city": "string or null"
  }}
}}

DOCUMENT TEXT:
{raw_text}

Return ONLY the JSON object, nothing else:"""
        
        return prompt
    
    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Clean JSON string
        """
        # Remove markdown code blocks if present
        text = response_text.strip()
        
        # Remove ```json and ``` markers
        if text.startswith('```json'):
            text = text[7:]  # Remove ```json
        elif text.startswith('```'):
            text = text[3:]  # Remove ```
        
        if text.endswith('```'):
            text = text[:-3]  # Remove trailing ```
        
        return text.strip()


# Global LLM service instance
llm_service = LLMService()
