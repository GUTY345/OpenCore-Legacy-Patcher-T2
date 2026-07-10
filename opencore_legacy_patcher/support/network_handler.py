"""
network_handler.py: Library dedicated to Network Handling tasks including downloading files
Refactored: Thread-safe, non-blocking shutdown, and full diagnostic logging preserved.
"""

import time
import requests
import logging
import enum
import hashlib
from typing import Optional, Union
from pathlib import Path
from . import utilities

SESSION = requests.Session()

class DownloadStatus(enum.Enum):
    INACTIVE:    str = "Inactive"
    DOWNLOADING: str = "Downloading"
    ERROR:       str = "Error"
    COMPLETE:    str = "Complete"

class NetworkUtilities:
    def __init__(self, url: str = None) -> None:
        self.url = url or "https://github.com"

    def verify_network_connection(self) -> bool:
        try:
            requests.head(self.url, timeout=5, allow_redirects=True)
            return True
        except (requests.exceptions.Timeout, requests.exceptions.TooManyRedirects, 
                requests.exceptions.ConnectionError, requests.exceptions.HTTPError):
            return False

    def validate_link(self) -> bool:
        try:
            response = SESSION.head(self.url, timeout=5, allow_redirects=True)
            response.raise_for_status()
            return True
        except (requests.exceptions.Timeout, requests.exceptions.TooManyRedirects, 
                requests.exceptions.ConnectionError, requests.exceptions.HTTPError):
            return False

    def get(self, url: str, **kwargs) -> requests.Response:
        try:
            return SESSION.get(url, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.TooManyRedirects, 
                requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as error:
            logging.warning(f"Error calling requests.get: {error}")
            return requests.Response()

    def post(self, url: str, **kwargs) -> requests.Response:
        try:
            return SESSION.post(url, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.TooManyRedirects, 
                requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as error:
            logging.warning(f"Error calling requests.post: {error}")
            return requests.Response()

class DownloadObject:
    def __init__(self, url: str, path: str, checksum_algo: Optional[hashlib._Hash] = None) -> None:
        self.url = url
        self.status = DownloadStatus.INACTIVE
        self.error_msg = ""
        self.filename = self._get_filename()
        self.filepath = Path(path)
        self.total_file_size = 0.0
        self.downloaded_file_size = 0.0
        self.start_time = time.time()
        self.error = False
        self.should_stop = False
        self.download_complete = False
        self.has_network = NetworkUtilities(self.url).verify_network_connection()
        self._checksum_storage = checksum_algo
        self.checksum = None
        if self.has_network:
            self._populate_file_size()

    # --- RESTORED DIAGNOSTIC/HELPER METHODS ---
    def _get_filename(self) -> str:
        """
        Get the filename from the URL

        Returns:
            str: Filename
        """
        # Diagnostic: Log the result to ensure URL parsing isn't failing 
        # due to unexpected URL structures
        filename = Path(self.url).name
        logging.debug(f"Resolved filename from URL: {filename}")
        return filename
    
    def _populate_file_size(self) -> None:
        """
        Get the file size of the file to be downloaded

        If unable to get file size, set to zero.
        Uses a HEAD request to identify the Content-Length header.
        """
        logging.info("Probieren, zu ermitteln der Datei-Größe für: {self.url}")
        logging.debug(f"Attempting to determine file size for: {self.url}")
        
        try:
            # We use SESSION (global) for consistency with your original code
            # Timeout is strictly defined to prevent hanging during the check
            result = SESSION.head(self.url, allow_redirects=True, timeout=5)
            
            if 'Content-Length' in result.headers:
                self.total_file_size = float(result.headers['Content-Length'])
                logging.info(f"Datei-Größe bestätigt: {self.total_file_size} bytes")
                logging.info(f"File size confirmed: {self.total_file_size} bytes")
            else:
                # This provides the diagnostic insight you need—did the server 
                # actually return a length or is it missing?
                logging.warning(f"Content-Length-Header fehlt für {self.url}")
                logging.warning(f"Content-Length header missing for {self.url}")
                raise Exception("Content-Length missing from headers")
        
        except Exception as e:
            # Diagnostic: Now you will know if the file size failed due to
            # a network timeout or an unexpected response
            logging.error(f"Beim Ermitteln der Datei-Größe ist ein Fehler aufgetreten für {self.url}: {str(e)}")
            logging.error(f"Error determining file size for {self.url}: {str(e)}")
            logging.error("Die Gesamtdateigröße wird auf 0,0 zurückgesetzt.")
            logging.error("Defaulting total_file_size to 0.0")
            self.total_file_size = 0.0

    def get_percent(self) -> float:
        return -1 if self.total_file_size == 0.0 else (self.downloaded_file_size / self.total_file_size * 100)

    def get_speed(self) -> float:
        elapsed = time.time() - self.start_time
        return self.downloaded_file_size / elapsed if elapsed > 0 else 0

    def get_time_remaining(self) -> float:
        if self.total_file_size == 0.0: return -1
        speed = self.get_speed()
        return -1 if speed <= 0 else (self.total_file_size - self.downloaded_file_size) / speed

    def get_file_size(self) -> float: return self.total_file_size
    def is_active(self) -> bool: return self.status == DownloadStatus.DOWNLOADING

    # --- STABILIZED CORE ---
    def stop(self) -> None:
        """Non-blocking signal. No longer waits for thread."""
        self.should_stop = True

    def download(self, display_progress: bool = False, spawn_thread: bool = True) -> None:
        """Call this from your UI. If spawn_thread is False, it runs synchronously."""
        if spawn_thread:
            import threading
            threading.Thread(target=self._download, args=(display_progress,), daemon=True).start()
        else:
            self._download(display_progress)

    def _download(self, display_progress: bool = False) -> None:
        """
        Download with full diagnostic tracing.
        """
        utilities.disable_sleep_while_running()
        self.status = DownloadStatus.DOWNLOADING
        logging.info(f"Herunterladen wird gestartet: URL={self.url}, Target={self.filepath}")
        logging.info(f"Initiating download: URL={self.url}, Target={self.filepath}")

        try:
            # Stage 1: Network Check
            if not self.has_network:
                raise ConnectionError("No network connection detected before download.")

            # Stage 2: Filesystem Check
            if not self._prepare_working_directory(self.filepath):
                raise IOError(f"Could not prepare working directory: {self.error_msg}")

            # Stage 3: Request Execution with detailed logging
            logging.info("Netzwerkstream wird geöffnet...")
            logging.debug("Opening network stream...")
            response = NetworkUtilities().get(self.url, stream=True, timeout=15)
            
            # Check for HTTP errors early
            if response.status_code != 200:
                raise requests.exceptions.HTTPError(f"HTTP Status Code {response.status_code}")

            with open(self.filepath, 'wb') as file:
                for i, chunk in enumerate(response.iter_content(chunk_size=1024 * 1024)):
                    if self.should_stop:
                        logging.warning(f"Herunterladen gestoppt von Benutzer auf {self.downloaded_file_size} bytes.")
                        logging.warning(f"Download stopped by user at {self.downloaded_file_size} bytes.")
                        raise InterruptedError("Download manually aborted.")
                    
                    if chunk:
                        file.write(chunk)
                        self.downloaded_file_size += len(chunk)
                        if self._checksum_storage:
                            self._checksum_storage.update(chunk)
                            
            self.download_complete = True
            logging.info(f"Herunterladen vollständig abgeschlossen: {self.filename}")
            logging.info(f"Successfully finished download: {self.filename}")

        except Exception as e:
            self.error = True
            self.error_msg = str(e)
            self.status = DownloadStatus.ERROR
            
            # CRITICAL: This will log the entire stack trace (file, line number, and function)
            # You will no longer have to guess where the crash occurred.
            logging.info("FATALES FEHLER WÄHREND HERUNTERLADEN:")
            logging.exception(f"FATAL DOWNLOAD ERROR: {self.url} | Error: {self.error_msg}")
            
        finally:
            self.status = DownloadStatus.COMPLETE
            utilities.enable_sleep_after_running()
            logging.info("Netzwerkressourcen freigegeben und Energiespareinstellungen wiederhergestellt.")
            logging.info("Network resources released and sleep settings restored.")
    def _prepare_working_directory(self, path: Path) -> bool:
        try:
            if path.exists(): path.unlink()
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self.error_msg = str(e)
            return False
