"""
AWS Textract service for document text extraction
"""
import boto3
from botocore.exceptions import ClientError
from app.config import settings
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class TextractService:
    """Service for AWS Textract operations"""
    
    def __init__(self):
        """Initialize Textract client"""
        self.textract_client = boto3.client(
            'textract',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.bucket_name = settings.s3_bucket_name
    
    def extract_text_from_s3(self, s3_key: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Extract text from document in S3 using Textract
        
        Args:
            s3_key: S3 key/path of the document
            
        Returns:
            Tuple of (extracted_text, confidence_score, error_message)
            - extracted_text: Combined text from all LINE blocks
            - confidence_score: Average confidence across all LINE blocks
            - error_message: Error description if extraction failed
        """
        try:
            logger.info(f"Starting Textract extraction for s3://{self.bucket_name}/{s3_key}")
            logger.info(f"Using AWS region: {settings.aws_region}")
            
            # First verify the S3 object exists and is accessible
            try:
                head_response = self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
                logger.info(f"S3 object verified: size={head_response['ContentLength']} bytes, "
                           f"content-type={head_response.get('ContentType', 'unknown')}")
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == '404':
                    error_msg = f"S3 object not found: s3://{self.bucket_name}/{s3_key}"
                elif error_code == 'Forbidden' or error_code == '403':
                    error_msg = f"Access denied to S3 object: s3://{self.bucket_name}/{s3_key}. Check IAM permissions."
                else:
                    error_msg = f"S3 head_object failed ({error_code}): {str(e)}"
                logger.error(error_msg)
                return None, None, error_msg
            
            # Call Textract detect_document_text
            response = self.textract_client.detect_document_text(
                Document={
                    'S3Object': {
                        'Bucket': self.bucket_name,
                        'Name': s3_key
                    }
                }
            )
            
            # Extract LINE blocks and compute confidence
            lines = []
            confidences = []
            
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    # Extract text
                    text = block.get('Text', '').strip()
                    if text:
                        lines.append(text)
                    
                    # Extract confidence
                    confidence = block.get('Confidence')
                    if confidence is not None:
                        confidences.append(confidence)
            
            # Combine lines into single text blob
            extracted_text = '\n'.join(lines)
            
            # Compute average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else None
            
            logger.info(
                f"Textract extraction completed: {len(lines)} lines, "
                f"avg confidence: {avg_confidence:.2f}%" if avg_confidence else "N/A"
            )
            
            return extracted_text, avg_confidence, None
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'InvalidS3ObjectException':
                error_msg = (
                    f"Textract cannot access S3 object. This usually means:\n"
                    f"1. The IAM user needs 's3:GetObject' permission on bucket '{self.bucket_name}'\n"
                    f"2. The IAM user needs 'textract:DetectDocumentText' permission\n"
                    f"3. The S3 bucket and Textract must be in the same region (currently: {settings.aws_region})\n"
                    f"Error: {error_message}"
                )
            elif error_code == 'AccessDeniedException':
                error_msg = f"Access denied to Textract API. Check IAM permissions for 'textract:DetectDocumentText'. Error: {error_message}"
            else:
                error_msg = f"Textract ClientError ({error_code}): {error_message}"
            
            logger.error(error_msg)
            return None, None, error_msg
            
        except Exception as e:
            error_msg = f"Textract extraction failed: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg


# Global Textract service instance
textract_service = TextractService()
