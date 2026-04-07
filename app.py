# app.py
import os
import uuid
import shutil
import subprocess
import logging
from flask import Flask, render_template, request, send_file, g
from PIL import Image

app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = "uploads"
app.config["COMPRESSED_FOLDER"] = "compressed"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["COMPRESSED_FOLDER"], exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_ghostscript_path():
    for cmd in ["gswin64c", "gswin32c", "gs"]:
        path = shutil.which(cmd)
        if path:
            return path
    fallback = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError("Ghostscript not found. Please install it and add to PATH.")


def compress_pdf(input_path, output_path):
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
        
        logger.info(f"✅ PDF: {os.path.basename(input_path)}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌  PDF: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"❌ unexpected error PDF: {e}")
        return False


@app.errorhandler(413)
def request_entity_too_large(error):
    return "📦 the file size is more than 10mp", 413


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"💥 Internal Server Error: {error}", exc_info=True)
    return "❌ something wrong ", 500


@app.after_request
def cleanup_temp_files(response):
    if hasattr(g, "files_to_cleanup"):
        for file_path in g.files_to_cleanup:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"⚠️can't remove the file: {file_path} | {e}")
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            if "file" not in request.files:
                return "📁 there is no file to compress", 400

            file = request.files["file"]
            if file.filename == "":
                return "📁 file name is empty", 400

            if not allowed_file(file.filename):
                return "🚫 only: PDF, JPG, PNG", 400

            original_filename = file.filename
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower()
            
            safe_internal_name = f"{uuid.uuid4()}{ext}"
            
            input_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_internal_name)
            file.save(input_path)

            output_path = os.path.join(app.config["COMPRESSED_FOLDER"], f"{safe_internal_name}")
            
            g.files_to_cleanup = list({input_path, output_path})

            if ext == ".pdf":
                if not compress_pdf(input_path, output_path):
                    logger.warning("⚠️the compression failed ")
                    output_path = input_path

            elif ext in [".jpg", ".jpeg"]:
                try:
                    with Image.open(input_path) as img:
                        img.convert("RGB").save(
                            output_path, "JPEG", quality=60, optimize=True, progressive=True
                        )
                except Exception as e:
                    logger.error(f"❌ problrm to comperssion JPEG: {e}")
                    output_path = input_path

            elif ext == ".png":
                try:
                    with Image.open(input_path) as img:
                        img.save(output_path, "PNG", optimize=True, compress_level=9)
                except Exception as e:
                    logger.error(f"❌ problrm to comperssion PNG: {e}")
                    output_path = input_path

            safe_name = original_filename.replace("/", "_").replace("\\", "_")
            download_name = f"{safe_name}"

            return send_file(
                output_path,
                as_attachment=True,
                download_name=download_name
            )

        except Exception as e:
            logger.error(f"💥 Unexpected Error: {type(e).__name__} - {e}", exc_info=True)
            return "❌ problem when file process.", 500

    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
