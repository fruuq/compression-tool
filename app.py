from flask import Flask, render_template, request, send_file
from PIL import Image
import os
import zipfile
import subprocess
import shutil
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
COMPRESSED_FOLDER = "compressed"

# 🔐 تحديد حجم الملف (10MB)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# 🔐 أنواع الملفات المسموحة
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def compress_pdf(input_path, output_path):
    gs_path = shutil.which("gswin64c")

    if gs_path is None:
        gs_path = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"

    try:
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

        return True

    except Exception as e:
        print("PDF Compression Error:", e)
        return False


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        if "file" not in request.files:
            return "No file part"

        file = request.files["file"]

        if file.filename == "":
            return "No file selected"

        # 🔐 تحقق من نوع الملف
        if not allowed_file(file.filename):
            return "File type not allowed"

        # 🔐 تنظيف الاسم + إضافة UUID
        filename = secure_filename(file.filename)
        unique_name = str(uuid.uuid4()) + "_" + filename

        input_path = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(input_path)

        name, ext = os.path.splitext(filename)
        ext = ext.lower()

        # PDF
        if ext == ".pdf":

            output_path = os.path.join(
                COMPRESSED_FOLDER, f"compressed_{unique_name}")

            success = compress_pdf(input_path, output_path)

            if not success:
                print("Compression failed, returning original file")
                output_path = input_path

        # Images
        elif ext in [".jpg", ".jpeg", ".png"]:

            output_path = os.path.join(
                COMPRESSED_FOLDER, f"compressed_{unique_name}")

            try:
                img = Image.open(input_path)

                if ext in [".jpg", ".jpeg"]:
                    img.save(output_path, "JPEG", quality=50, optimize=True)
                else:
                    img.save(output_path, "PNG", optimize=True)

            except Exception as e:
                print("Image Error:", e)
                output_path = input_path

        # (ما عاد في ZIP لأي ملفات غريبة ❌)

        response = send_file(output_path, as_attachment=True)

        # 🔐 حذف الملفات
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            print("Cleanup Error:", e)

        return response

    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)