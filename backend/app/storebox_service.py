import io
import zipfile
import requests

from .kvitteringer_service import replace_storebox_upload


def _extract_json_from_zip(zip_bytes: bytes) -> bytes:
    """Extracts the receipts.json file from a Storebox data export ZIP in memory."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            # Locate receipts.json, even if it's nested inside a folder
            target_file = None
            for name in z.namelist():
                if name.lower().endswith("receipts.json"):
                    target_file = name
                    break
            
            if not target_file:
                raise ValueError("Could not find receipts.json in the downloaded ZIP file.")
            
            with z.open(target_file) as f:
                return f.read()
    except zipfile.BadZipFile:
        raise ValueError("The provided link or file is not a valid ZIP archive.")


def process_storebox_link(url: str) -> dict[str, object]:
    """Downloads a Storebox ZIP export from a pre-signed URL and processes the JSON."""
    if not url or not url.startswith("http"):
        raise ValueError("Invalid URL provided.")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Failed to download from link: {e}")

    zip_bytes = response.content
    json_bytes = _extract_json_from_zip(zip_bytes)
    
    # Import into Peng
    return replace_storebox_upload(json_bytes, "receipts-upload.json")


def process_storebox_file(content: bytes, filename: str) -> dict[str, object]:
    """Processes an uploaded Storebox ZIP or JSON file from memory."""
    # Check if it's a ZIP by magic bytes or filename extension
    if filename.lower().endswith(".zip") or content.startswith(b"PK\x03\x04"):
        json_bytes = _extract_json_from_zip(content)
    else:
        # Assume it's a direct upload of the receipts.json file
        json_bytes = content

    return replace_storebox_upload(json_bytes, "receipts-upload.json")
