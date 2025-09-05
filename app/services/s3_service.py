import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.client import Config
from typing import Dict, Optional, List
import uuid
import mimetypes
from datetime import datetime, timedelta
import logging
import os
import json

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for handling AWS S3 operations with pre-signed URLs"""
    
    def __init__(self):
        self._s3_client = None
        self._bucket_name = settings.S3_BUCKET_NAME
        self._content_prefix = settings.S3_CONTENT_PREFIX
        self._static_credentials = None
        
    @property
    def _client(self):
        """Alias for s3_client for backward compatibility"""
        return self.s3_client
    
    @property
    def s3_client(self):
        """Lazy initialization of S3 client"""
        if self._s3_client is None:
            try:
                # Configure S3 client
                config = Config(
                    region_name=settings.AWS_REGION,
                    signature_version='s3v4',
                    s3={
                        'addressing_style': 'virtual'
                    }
                )
                
                # Get static credentials from Secrets Manager or environment
                credentials = self._get_static_credentials()
                
                if credentials:
                    self._s3_client = boto3.client(
                        's3',
                        aws_access_key_id=credentials['AWS_ACCESS_KEY_ID'],
                        aws_secret_access_key=credentials['AWS_SECRET_ACCESS_KEY'],
                        region_name=settings.AWS_REGION,
                        config=config
                    )
                else:
                    # Use default credentials (IAM role, AWS CLI, environment variables)
                    self._s3_client = boto3.client('s3', config=config)
                    
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                raise
                
        return self._s3_client
    
    def _get_static_credentials(self) -> Optional[Dict[str, str]]:
        """Get static S3 credentials from Secrets Manager or environment variables"""
        if self._static_credentials:
            logger.info(f"Using cached S3 credentials: {self._static_credentials['AWS_ACCESS_KEY_ID'][:8]}...")
            return self._static_credentials
        
        # Try environment variables first (Lambda uses S3_* to avoid conflicts)
        aws_access_key = os.getenv('S3_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY_ID') or settings.AWS_ACCESS_KEY_ID
        aws_secret_key = os.getenv('S3_SECRET_ACCESS_KEY') or os.getenv('AWS_SECRET_ACCESS_KEY') or settings.AWS_SECRET_ACCESS_KEY
        
        if aws_access_key and aws_secret_key:
            logger.info(f"Using environment S3 credentials: {aws_access_key[:8]}...")
            self._static_credentials = {
                'AWS_ACCESS_KEY_ID': aws_access_key,
                'AWS_SECRET_ACCESS_KEY': aws_secret_key
            }
            return self._static_credentials
        
        # Try Secrets Manager for static credentials
        try:
            logger.info("Attempting to retrieve S3 credentials from Secrets Manager...")
            secrets_client = boto3.client('secretsmanager', region_name=settings.AWS_REGION)
            response = secrets_client.get_secret_value(SecretId='musically/s3-credentials')
            
            if 'SecretString' in response:
                credentials = json.loads(response['SecretString'])
                logger.info(f"Using Secrets Manager S3 credentials: {credentials['AWS_ACCESS_KEY_ID'][:8]}...")
                self._static_credentials = credentials
                return credentials
        except Exception as e:
            logger.warning(f"Could not retrieve S3 credentials from Secrets Manager: {e}")
        
        logger.warning("No static S3 credentials found, falling back to IAM role")
        return None
    
    def _refresh_client(self):
        """Force refresh of S3 client to get new credentials"""
        logger.info("Refreshing S3 client due to expired credentials")
        self._s3_client = None
        self._static_credentials = None  # Clear cached credentials
        # Force a new session to refresh credential providers
        boto3.setup_default_session()
    
    def _execute_with_retry(self, operation_func, *args, **kwargs):
        """Execute S3 operation with automatic credential refresh on expiration"""
        try:
            return operation_func(*args, **kwargs)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['InvalidAccessKeyId', 'TokenExpired', 'ExpiredToken']:
                logger.warning(f"AWS credentials expired ({error_code}), refreshing client and retrying...")
                self._refresh_client()
                # Retry once with refreshed credentials
                return operation_func(*args, **kwargs)
            else:
                raise
        except NoCredentialsError:
            logger.warning("No AWS credentials found, refreshing client and retrying...")
            self._refresh_client()
            return operation_func(*args, **kwargs)
    
    def generate_upload_presigned_url(
        self,
        user_id: str,
        filename: str,
        content_type: str,
        file_size: int,
        expire_seconds: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Generate a pre-signed URL for uploading a file to S3
        
        Args:
            user_id: ID of the user uploading the file
            filename: Original filename
            content_type: MIME type of the file
            file_size: Size of the file in bytes
            expire_seconds: URL expiration time in seconds
            
        Returns:
            Dictionary containing upload URL and metadata
        """
        return self._execute_with_retry(self._generate_upload_presigned_url_internal, 
                                       user_id, filename, content_type, file_size, expire_seconds)
    
    def _generate_upload_presigned_url_internal(
        self,
        user_id: str,
        filename: str,
        content_type: str,
        file_size: int,
        expire_seconds: Optional[int] = None
    ) -> Dict[str, str]:
        """Internal method for generating upload presigned URL"""
        try:
            expire_seconds = expire_seconds or settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
            
            # Generate unique key for the file
            file_extension = filename.split('.')[-1] if '.' in filename else ''
            unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())
            s3_key = f"{self._content_prefix}{user_id}/{unique_filename}"
            
            # Prepare conditions for the presigned POST
            conditions = [
                {"bucket": self._bucket_name},
                {"key": s3_key},
                {"Content-Type": content_type},
                ["content-length-range", 1, file_size * 2]  # Allow up to 2x the reported size
            ]
            
            # Generate presigned POST URL
            response = self.s3_client.generate_presigned_post(
                Bucket=self._bucket_name,
                Key=s3_key,
                Fields={
                    "Content-Type": content_type,
                },
                Conditions=conditions,
                ExpiresIn=expire_seconds
            )
            
            return {
                "upload_url": response["url"],
                "fields": response["fields"],
                "s3_key": s3_key,
                "bucket": self._bucket_name,
                "expires_in": expire_seconds,
                "file_url": f"s3://{self._bucket_name}/{s3_key}"
            }
            
        except Exception as e:
            logger.error(f"Failed to generate upload presigned URL: {e}")
            raise
    
    def generate_download_presigned_url(
        self,
        s3_key: str,
        expire_seconds: Optional[int] = None,
        content_disposition: Optional[str] = None
    ) -> str:
        """
        Generate a pre-signed URL for downloading a file from S3
        
        Args:
            s3_key: S3 key of the file
            expire_seconds: URL expiration time in seconds
            content_disposition: Content-Disposition header for download
            
        Returns:
            Pre-signed download URL
        """
        return self._execute_with_retry(self._generate_download_presigned_url_internal,
                                       s3_key, expire_seconds, content_disposition)
    
    def _generate_download_presigned_url_internal(
        self,
        s3_key: str,
        expire_seconds: Optional[int] = None,
        content_disposition: Optional[str] = None
    ) -> str:
        """Internal method for generating download presigned URL"""
        try:
            expire_seconds = expire_seconds or settings.S3_DOWNLOAD_URL_EXPIRE_SECONDS
            
            params = {
                'Bucket': self._bucket_name,
                'Key': s3_key
            }
            
            # Add content disposition if provided
            if content_disposition:
                params['ResponseContentDisposition'] = content_disposition
            
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expire_seconds
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to generate download presigned URL: {e}")
            raise
    
    def check_file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            s3_key: S3 key of the file
            
        Returns:
            True if file exists, False otherwise
        """
        return self._execute_with_retry(self._check_file_exists_internal, s3_key)
    
    def _check_file_exists_internal(self, s3_key: str) -> bool:
        """Internal method for checking file existence"""
        try:
            self.s3_client.head_object(Bucket=self._bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking file existence: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error checking file existence: {e}")
            raise
    
    def get_file_metadata(self, s3_key: str) -> Optional[Dict]:
        """
        Get metadata for a file in S3
        
        Args:
            s3_key: S3 key of the file
            
        Returns:
            Dictionary containing file metadata or None if file doesn't exist
        """
        return self._execute_with_retry(self._get_file_metadata_internal, s3_key)
    
    def _get_file_metadata_internal(self, s3_key: str) -> Optional[Dict]:
        """Internal method for getting file metadata"""
        try:
            response = self.s3_client.head_object(Bucket=self._bucket_name, Key=s3_key)
            
            return {
                "size": response.get('ContentLength', 0),
                "content_type": response.get('ContentType', ''),
                "last_modified": response.get('LastModified'),
                "etag": response.get('ETag', '').strip('"'),
                "metadata": response.get('Metadata', {})
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            else:
                logger.error(f"Error getting file metadata: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error getting file metadata: {e}")
            raise
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            s3_key: S3 key of the file to delete
            
        Returns:
            True if file was deleted successfully
        """
        return self._execute_with_retry(self._delete_file_internal, s3_key)
    
    def _delete_file_internal(self, s3_key: str) -> bool:
        """Internal method for deleting file"""
        try:
            self.s3_client.delete_object(Bucket=self._bucket_name, Key=s3_key)
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            raise
    
    def list_user_files(self, user_id: str, max_keys: int = 1000) -> List[Dict]:
        """
        List all files for a specific user
        
        Args:
            user_id: ID of the user
            max_keys: Maximum number of files to return
            
        Returns:
            List of file information dictionaries
        """
        return self._execute_with_retry(self._list_user_files_internal, user_id, max_keys)
    
    def _list_user_files_internal(self, user_id: str, max_keys: int = 1000) -> List[Dict]:
        """Internal method for listing user files"""
        try:
            prefix = f"{self._content_prefix}{user_id}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self._bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'],
                    "etag": obj['ETag'].strip('"')
                })
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing user files: {e}")
            raise
    
    def validate_file_type(self, content_type: str) -> tuple[bool, str]:
        """
        Validate if the file type is allowed
        
        Args:
            content_type: MIME type of the file
            
        Returns:
            Tuple of (is_valid, media_type)
        """
        allowed_audio_types = {
            "audio/mpeg", "audio/wav", "audio/ogg", 
            "audio/m4a", "audio/aac", "audio/mp3"
        }
        
        allowed_video_types = {
            "video/mp4", "video/avi", "video/mov", 
            "video/wmv", "video/webm", "video/quicktime"
        }
        
        if content_type in allowed_audio_types:
            return True, "audio"
        elif content_type in allowed_video_types:
            return True, "video"
        else:
            return False, ""
    
    def extract_s3_key_from_url(self, s3_url: str) -> Optional[str]:
        """
        Extract S3 key from various S3 URL formats
        
        Args:
            s3_url: S3 URL (s3://, https://, etc.)
            
        Returns:
            S3 key or None if invalid URL
        """
        try:
            if s3_url.startswith('s3://'):
                # Format: s3://bucket/key
                parts = s3_url[5:].split('/', 1)
                if len(parts) == 2 and parts[0] == self._bucket_name:
                    return parts[1]
            elif 'amazonaws.com' in s3_url:
                # Format: https://bucket.s3.region.amazonaws.com/key
                # or: https://s3.region.amazonaws.com/bucket/key
                if f"{self._bucket_name}.s3" in s3_url:
                    # Virtual hosted-style
                    key = s3_url.split(f"{self._bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/")[1]
                    return key
                elif f"s3.{settings.AWS_REGION}.amazonaws.com/{self._bucket_name}/" in s3_url:
                    # Path-style
                    key = s3_url.split(f"s3.{settings.AWS_REGION}.amazonaws.com/{self._bucket_name}/")[1]
                    return key
            
            return None
            
        except Exception:
            return None


# Global S3 service instance
s3_service = S3Service()