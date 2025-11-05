#!/usr/bin/env python3
import os
import time
import boto3
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transfer.log'),
        logging.StreamHandler()
    ]
)

class S3Uploader(FileSystemEventHandler):
    def __init__(self, watch_dir, bucket_name, s3_prefix=''):
        self.watch_dir = Path(watch_dir)
        self.bucket_name = bucket_name
        self.s3_prefix = s3_prefix
        self.s3_client = boto3.client('s3')
        self.uploaded_count = 0
        self.uploaded_bytes = 0
        
    def on_closed(self, event):
        """Triggered when file is closed after writing"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Skip hidden files and temp files
        if file_path.name.startswith('.') or file_path.name.endswith('.tmp'):
            logging.debug(f"Skipping {file_path}")
            return
            
        self.upload_and_delete(file_path)
    
    def upload_and_delete(self, file_path):
        """Upload file to S3 and delete local copy"""
        try:
            file_size = file_path.stat().st_size
            relative_path = file_path.relative_to(self.watch_dir)
            s3_key = f"{self.s3_prefix}/{relative_path}" if self.s3_prefix else str(relative_path)
            
            logging.info(f"📤 Uploading: {file_path.name} ({file_size / (1024**2):.2f} MB)")
            
            start_time = time.time()
            
            # Upload with progress
            self.s3_client.upload_file(
                str(file_path),
                self.bucket_name,
                s3_key,
                Callback=lambda bytes: self._progress_callback(bytes, file_size)
            )
            
            elapsed = time.time() - start_time
            speed = file_size / elapsed / (1024**2) if elapsed > 0 else 0
            
            logging.info(f"✅ Uploaded: {file_path.name} in {elapsed:.2f}s ({speed:.2f} MB/s)")
            
            # Verify upload
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            s3_size = response['ContentLength']
            
            if s3_size == file_size:
                file_path.unlink()
                self.uploaded_count += 1
                self.uploaded_bytes += file_size
                logging.info(f"🗑️  Deleted: {file_path.name}")
                logging.info(f"📊 Total: {self.uploaded_count} files, {self.uploaded_bytes / (1024**3):.2f} GB")
            else:
                logging.error(f"❌ Size mismatch for {file_path.name}: local={file_size}, s3={s3_size}")
                
        except Exception as e:
            logging.error(f"❌ Error uploading {file_path}: {e}")
    
    def _progress_callback(self, bytes_transferred, total_bytes):
        """Show upload progress for large files"""
        if total_bytes > 100 * 1024 * 1024:  # Only for files >100MB
            percent = (bytes_transferred / total_bytes) * 100
            if int(percent) % 10 == 0:  # Log every 10%
                logging.debug(f"Progress: {percent:.0f}%")

def upload_existing_files(watch_dir, uploader):
    """Upload any files already in directory"""
    logging.info("🔍 Checking for existing files...")
    watch_path = Path(watch_dir)
    
    for file_path in watch_path.rglob('*'):
        if file_path.is_file() and not file_path.name.startswith('.'):
            uploader.upload_and_delete(file_path)

if __name__ == "__main__":
    WATCH_DIR = os.path.expanduser("~/globus-transfer")
    BUCKET_NAME = "mm-mind2web"
    S3_PREFIX = ""  # Optional: prefix for S3 keys
    
    # Create watch directory if it doesn't exist
    Path(WATCH_DIR).mkdir(parents=True, exist_ok=True)
    
    logging.info(f"🚀 Starting S3 uploader")
    logging.info(f"📁 Watching: {WATCH_DIR}")
    logging.info(f"☁️  S3 Bucket: s3://{BUCKET_NAME}/{S3_PREFIX}")
    
    # Create uploader and handle existing files
    uploader = S3Uploader(WATCH_DIR, BUCKET_NAME, S3_PREFIX)
    upload_existing_files(WATCH_DIR, uploader)
    
    # Start watching for new files
    observer = Observer()
    observer.schedule(uploader, WATCH_DIR, recursive=True)
    observer.start()
    
    logging.info("👀 Watching for new files... (Ctrl+C to stop)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("🛑 Stopping uploader...")
    
    observer.join()
    logging.info(f"✨ Final stats: {uploader.uploaded_count} files, {uploader.uploaded_bytes / (1024**3):.2f} GB")
