"""Google Drive connector for uploading files."""

import logging
from dataclasses import dataclass
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a Google Drive upload operation."""
    
    success: bool
    file_id: str | None
    folder_id: str | None
    error: str | None


def upload_file(
    filepath: str,
    folder_id: str,
    credentials_path: str = "credentials.json"
) -> UploadResult:
    """
    Upload file to Google Drive folder.
    
    Uses service account authentication from credentials.json.
    
    Args:
        filepath: Path to the file to upload
        folder_id: Google Drive folder ID to upload to
        credentials_path: Path to service account credentials JSON
    
    Returns:
        UploadResult with success status and file/folder IDs or error message
    """
    try:
        # Validate file exists
        file_path = Path(filepath)
        if not file_path.exists():
            error_msg = f"File not found: {filepath}"
            logger.error(error_msg)
            return UploadResult(
                success=False,
                file_id=None,
                folder_id=folder_id,
                error=error_msg
            )
        
        # Load service account credentials
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        
        # Build Drive service
        service = build("drive", "v3", credentials=credentials)
        
        # Prepare file metadata
        file_metadata = {
            "name": file_path.name,
            "parents": [folder_id]
        }
        
        # Determine MIME type based on file extension
        mime_type = "text/csv" if file_path.suffix.lower() == ".csv" else "application/octet-stream"
        
        # Create media upload
        media = MediaFileUpload(
            filepath,
            mimetype=mime_type,
            resumable=True
        )
        
        # Execute upload (supportsAllDrives for Shared Drives)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        uploaded_file_id = file.get("id")
        
        logger.info(
            f"Successfully uploaded file to Google Drive. "
            f"File ID: {uploaded_file_id}, Folder ID: {folder_id}"
        )
        
        return UploadResult(
            success=True,
            file_id=uploaded_file_id,
            folder_id=folder_id,
            error=None
        )
        
    except FileNotFoundError as e:
        error_msg = f"Credentials file not found: {credentials_path}"
        logger.error(error_msg)
        return UploadResult(
            success=False,
            file_id=None,
            folder_id=folder_id,
            error=error_msg
        )
    except Exception as e:
        error_msg = f"Failed to upload file to Google Drive: {str(e)}"
        logger.error(error_msg)
        return UploadResult(
            success=False,
            file_id=None,
            folder_id=folder_id,
            error=error_msg
        )
