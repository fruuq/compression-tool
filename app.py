# app.py
import os
import uuid
import shutil
import subprocess
import logging
from flask import Flask, render_template, request, send_file, g
from PIL import Image

app = Flask(__name__)

# ⚙️ Application Configuration
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["COMPRESSED_FOLDER"] = "compressed_output"  # Separate folder for compressed files
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 🔒 Max file size: 10 MB
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

# Create folders automatically
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["COMPRESSED_FOLDER"], exist_ok=True)

# 📝 Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    """Check if the file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_ghostscript_path():
    """Find Ghostscript path compatible with all systems"""
    for cmd in ["gswin64c", "gswin32c", "gs"]:
        path = shutil.which(cmd)
        if path:
            return path
    # Fallback path for Windows
    fallback = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError("Ghostscript not found. Please install it and add to PATH.")


def compress_pdf(input_path, output_path):
    """Compress PDF file using Ghostscript"""
    try:
        gs_path = get_ghostscript_path()
        subprocess.run([
            gs_path,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/screen",
            "-dDownsampleColorImages=true",
            "-dColorImageResolution=72",
            "-dNOPAUSE",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ], check=True, capture_output=True, text=True)
        
        logger.info(f"✅ PDF compressed successfully: {os.path.basename(input_path)}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to compress PDF: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error while compressing PDF: {e}")
        return False


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return "📦 File size exceeds 10 MB. Please choose a smaller file.", 413


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors with a user-friendly message"""
    logger.error(f"💥 Internal Server Error: {error}", exc_info=True)
    return "❌ An internal server error occurred. Please try again later.", 500


@app.after_request
def cleanup_temp_files(response):
    """🗑️ Delete temporary files after sending response to client"""
    if hasattr(g, "files_to_cleanup"):
        for file_path in g.files_to_cleanup:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"⚠️ Could not delete file: {file_path} | {e}")
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            # 1. Check if file exists in request
            if "file" not in request.files:
                return "📁 No file was attached.", 400

            file = request.files["file"]
            if file.filename == "":
                return "📁 Filename is empty.", 400

            # 2. Validate file type
            if not allowed_file(file.filename):
                return "🚫 Unsupported file type. Allowed: PDF, JPG, PNG", 400

            # 3. Prepare paths
            original_filename = file.filename  # Keep original filename (Arabic/English/numbers)
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower()
            
            # Internal safe name for storage (UUID) - prevents conflicts
            safe_internal_name = f"{uuid.uuid4()}{ext}"
            
            input_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_internal_name)
            output_path = os.path.join(app.config["COMPRESSED_FOLDER"], safe_internal_name)
            
            # Save uploaded file with UUID name
            file.save(input_path)

            # Register files for automatic cleanup later
            g.files_to_cleanup = list({input_path, output_path})

            # 4. Compression process based on file type
            if ext == ".pdf":
                if not compress_pdf(input_path, output_path):
                    logger.warning("⚠️ PDF compression failed, sending original file.")
                    output_path = input_path

            elif ext in [".jpg", ".jpeg"]:
                try:
                    with Image.open(input_path) as img:
                        img.convert("RGB").save(
                            output_path, "JPEG", quality=60, optimize=True, progressive=True
                        )
                except Exception as e:
                    logger.error(f"❌ Error compressing JPEG: {e}")
                    output_path = input_path

            elif ext == ".png":
                try:
                    with Image.open(input_path) as img:
                        img.save(output_path, "PNG", optimize=True, compress_level=9)
                except Exception as e:
                    logger.error(f"❌ Error compressing PNG: {e}")
                    output_path = input_path

            # ✅ 5. Prepare download name: preserve original filename exactly (Arabic/English/numbers)
            # Sanitize only path separators to prevent directory traversal
            safe_download_name = original_filename.replace("/", "_").replace("\\", "_")

            # 6. Send file with original filename - no suffix added by browser
            return send_file(
                output_path,
                as_attachment=True,
                download_name=safe_download_name,  # This ensures exact original name in download
                mimetype="application/octet-stream"  # Force download for all file types
            )

        except Exception as e:
            logger.error(f"💥 Unexpected Error: {type(e).__name__} - {e}", exc_info=True)
            return "❌ An unexpected error occurred while processing the file.", 500

    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)