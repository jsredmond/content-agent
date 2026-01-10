"""Unit tests for Google Drive connector."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.connectors.google_drive import UploadResult, upload_file


class TestUploadResult:
    """Tests for UploadResult dataclass."""
    
    def test_success_result(self):
        """Test creating a successful upload result."""
        result = UploadResult(
            success=True,
            file_id="abc123",
            folder_id="folder456",
            error=None
        )
        assert result.success is True
        assert result.file_id == "abc123"
        assert result.folder_id == "folder456"
        assert result.error is None
    
    def test_failure_result(self):
        """Test creating a failed upload result."""
        result = UploadResult(
            success=False,
            file_id=None,
            folder_id="folder456",
            error="Upload failed"
        )
        assert result.success is False
        assert result.file_id is None
        assert result.folder_id == "folder456"
        assert result.error == "Upload failed"


class TestUploadFile:
    """Tests for upload_file function."""
    
    def test_file_not_found(self, caplog):
        """Test handling of non-existent file."""
        with caplog.at_level(logging.ERROR):
            result = upload_file(
                filepath="/nonexistent/file.csv",
                folder_id="folder123"
            )
        
        assert result.success is False
        assert result.file_id is None
        assert result.folder_id == "folder123"
        assert "File not found" in result.error
        assert "File not found" in caplog.text
    
    def test_credentials_not_found(self, caplog):
        """Test handling of missing credentials file."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n1,2")
            temp_path = f.name
        
        try:
            with caplog.at_level(logging.ERROR):
                result = upload_file(
                    filepath=temp_path,
                    folder_id="folder123",
                    credentials_path="/nonexistent/credentials.json"
                )
            
            assert result.success is False
            assert result.file_id is None
            assert result.folder_id == "folder123"
            assert result.error is not None
        finally:
            Path(temp_path).unlink()
    
    @patch("src.connectors.google_drive.build")
    @patch("src.connectors.google_drive.service_account.Credentials.from_service_account_file")
    @patch("src.connectors.google_drive.MediaFileUpload")
    def test_successful_upload(self, mock_media, mock_creds, mock_build, caplog):
        """Test successful file upload logs file ID."""
        # Setup mocks
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files().create().execute.return_value = {"id": "uploaded_file_123"}
        
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n1,2")
            temp_path = f.name
        
        try:
            with caplog.at_level(logging.INFO):
                result = upload_file(
                    filepath=temp_path,
                    folder_id="folder456",
                    credentials_path="credentials.json"
                )
            
            assert result.success is True
            assert result.file_id == "uploaded_file_123"
            assert result.folder_id == "folder456"
            assert result.error is None
            assert "uploaded_file_123" in caplog.text
            assert "folder456" in caplog.text
        finally:
            Path(temp_path).unlink()
    
    @patch("src.connectors.google_drive.build")
    @patch("src.connectors.google_drive.service_account.Credentials.from_service_account_file")
    @patch("src.connectors.google_drive.MediaFileUpload")
    def test_upload_api_error(self, mock_media, mock_creds, mock_build, caplog):
        """Test handling of API errors during upload."""
        # Setup mocks
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files().create().execute.side_effect = Exception("API Error: quota exceeded")
        
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n1,2")
            temp_path = f.name
        
        try:
            with caplog.at_level(logging.ERROR):
                result = upload_file(
                    filepath=temp_path,
                    folder_id="folder456",
                    credentials_path="credentials.json"
                )
            
            assert result.success is False
            assert result.file_id is None
            assert result.folder_id == "folder456"
            assert "API Error" in result.error or "quota exceeded" in result.error
            assert "Failed to upload" in caplog.text
        finally:
            Path(temp_path).unlink()
    
    @patch("src.connectors.google_drive.build")
    @patch("src.connectors.google_drive.service_account.Credentials.from_service_account_file")
    @patch("src.connectors.google_drive.MediaFileUpload")
    def test_upload_uses_correct_mime_type_for_csv(self, mock_media, mock_creds, mock_build):
        """Test that CSV files use text/csv MIME type."""
        mock_creds.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files().create().execute.return_value = {"id": "file123"}
        
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"test,data\n1,2")
            temp_path = f.name
        
        try:
            upload_file(
                filepath=temp_path,
                folder_id="folder456",
                credentials_path="credentials.json"
            )
            
            # Verify MediaFileUpload was called with correct MIME type
            mock_media.assert_called_once()
            call_kwargs = mock_media.call_args
            assert call_kwargs[1]["mimetype"] == "text/csv"
        finally:
            Path(temp_path).unlink()
