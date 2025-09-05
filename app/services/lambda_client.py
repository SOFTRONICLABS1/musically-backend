import boto3
import json
import logging
from typing import Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class LambdaClient:
    """Client for invoking other Lambda functions"""
    
    def __init__(self):
        self._lambda_client = None
        self._music_extraction_function_name = f"musically-api-{settings.STAGE}-firebase-auth"
    
    @property
    def lambda_client(self):
        """Lazy initialization of Lambda client"""
        if self._lambda_client is None:
            self._lambda_client = boto3.client('lambda', region_name=settings.AWS_REGION)
        return self._lambda_client
    
    def invoke_music_extraction(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Invoke the firebase-auth Lambda to extract music from URL
        
        Args:
            url: Social media URL to extract music from
            
        Returns:
            Extracted music data or None if failed
        """
        try:
            payload = {
                "httpMethod": "POST",
                "path": "/api/v1/music/extract",
                "queryStringParameters": {"url": url},
                "headers": {"Content-Type": "application/json"}
            }
            
            response = self.lambda_client.invoke(
                FunctionName=self._music_extraction_function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            response_payload = json.loads(response['Payload'].read())
            
            # Parse the HTTP response
            if response_payload.get('statusCode') == 200:
                body = json.loads(response_payload.get('body', '{}'))
                if body.get('success'):
                    return {
                        'metadata': body.get('metadata'),
                        'notes_data': body.get('notes_data'),
                        'is_music_content': body.get('is_music_content', False)
                    }
            
            # Log error details
            error_body = json.loads(response_payload.get('body', '{}'))
            logger.error(f"Music extraction Lambda failed: {error_body.get('error', 'Unknown error')}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to invoke music extraction Lambda: {e}")
            return None
    
    def validate_youtube_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Validate YouTube URL using the firebase-auth Lambda
        
        Args:
            url: YouTube URL to validate
            
        Returns:
            Validation result or None if failed
        """
        try:
            payload = {
                "httpMethod": "POST",
                "path": "/api/v1/music/validate-youtube",
                "queryStringParameters": {"url": url},
                "headers": {"Content-Type": "application/json"}
            }
            
            response = self.lambda_client.invoke(
                FunctionName=self._music_extraction_function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            response_payload = json.loads(response['Payload'].read())
            
            if response_payload.get('statusCode') == 200:
                body = json.loads(response_payload.get('body', '{}'))
                if body.get('success'):
                    return body
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to validate YouTube URL: {e}")
            return None


# Global instance
lambda_client = LambdaClient()