from flask import Flask, render_template, request, send_file
from PIL import Image
import os
import zipfile
import subprocess

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
COMPRESSED_FOLDER = "compressed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)

GS_PATH = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe" 

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["file"]
        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)

        filename, ext = os.path.splitext(file.filename)
        ext = ext.lower()

        # PDF compression using Ghostscript
        if ext == ".pdf":
            output_path = os.path.join(COMPRESSED_FOLDER, f"compressed_{file.filename}")
            try:
                subprocess.run([
                    "gs",
                    "-sDEVICE=pdfwrite",
                    "-dCompatibilityLevel=1.4",
                    "-dPDFSETTINGS=/ebook",
                    "-dNOPAUSE",
                    "-dQUIET",
                    "-dBATCH",
                    f"-sOutputFile={output_path}",
                    input_path
                ])
            except:
                output_path = input_path

        # Image compression
        elif ext in [".jpg", ".jpeg", ".png"]:
            output_path = os.path.join(COMPRESSED_FOLDER, f"compressed_{file.filename}")
            img = Image.open(input_path)
            if ext in [".jpg", ".jpeg"]:
                img.save(output_path, "JPEG", quality=70, optimize=True)
            else:
                img.save(output_path, "PNG", optimize=True)

        else:  # Other files
            output_path = os.path.join(COMPRESSED_FOLDER, f"compressed_{file.filename}.zip")
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(input_path, arcname=file.filename)

        return send_file(output_path, as_attachment=True)

    return render_template("index.html")

if __name__ == "__main__":
   
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)