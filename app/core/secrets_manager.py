import boto3
import json
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class SecretsManager:
    def __init__(self):
        self.client = None
        self.cached_secret = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize AWS Secrets Manager client"""
        try:
            session = boto3.session.Session()
            self.client = session.client(
                service_name='secretsmanager',
                region_name=settings.AWS_REGION
            )
        except Exception as e:
            logger.warning(f"Could not initialize AWS Secrets Manager: {e}")
    
    def get_secret(self, secret_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve secret from AWS Secrets Manager
        Falls back to local SECRET_KEY if AWS is not available
        """
        if self.cached_secret:
            return self.cached_secret
        
        secret_name = secret_name or settings.AWS_SECRET_NAME
        
        if not self.client:
            logger.info("Using local SECRET_KEY as AWS Secrets Manager is not configured")
            return {"jwt_secret": settings.SECRET_KEY}
        
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            
            if 'SecretString' in response:
                secret = json.loads(response['SecretString'])
            else:
                # Binary secret
                secret = json.loads(response['SecretBinary'])
            
            self.cached_secret = secret
            return secret
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                logger.error(f"Secret {secret_name} not found")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request for secret {secret_name}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter for secret {secret_name}")
            else:
                logger.error(f"Error retrieving secret: {e}")
            
            # Fallback to local secret
            logger.info("Falling back to local SECRET_KEY")
            return {"jwt_secret": settings.SECRET_KEY}
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret: {e}")
            return {"jwt_secret": settings.SECRET_KEY}
    
    def get_jwt_secret(self) -> str:
        """Get JWT secret specifically"""
        secrets = self.get_secret()
        return secrets.get("jwt_secret", settings.SECRET_KEY)


# Singleton instance
secrets_manager = SecretsManager()