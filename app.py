import os
import uuid
import shutil
import subprocess
import logging
from flask import Flask, render_template, request, send_file, g
from PIL import Image
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)

# ⚙️ إعدادات التطبيق
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["COMPRESSED_FOLDER"] = "compressed"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 🔒 10 ميجا كحد أقصى
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["COMPRESSED_FOLDER"], exist_ok=True)

# 📝 إعداد نظام السجلات بدلًا من print
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_ghostscript_path():
    """البحث عن مسار Ghostscript بشكل متوافق مع جميع الأنظمة"""
    for cmd in ["gswin64c", "gswin32c", "gs"]:
        path = shutil.which(cmd)
        if path:
            return path
    # مسار احتياطي لويندوز في حال عدم إضافته للـ PATH
    fallback = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError("لم يتم العثور على Ghostscript. يرجى تثبيته وإضافته إلى متغير النظام PATH.")


def compress_pdf(input_path, output_path):
    gs_path = get_ghostscript_path()
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
        logger.info(f"✅ تم ضغط PDF بنجاح: {os.path.basename(input_path)}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ فشل ضغط PDF: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع أثناء ضغط PDF: {e}")
        return False


@app.errorhandler(413)
def request_entity_too_large(error):
    return "📦 حجم الملف يتجاوز 10 ميجا. يرجى اختيار ملف أصغر.", 413


@app.after_request
def cleanup_temp_files(response):
    """🗑️ حذف الملفات المؤقتة بعد إرسال الاستجابة للعميل"""
    if hasattr(g, "files_to_cleanup"):
        for file_path in g.files_to_cleanup:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"⚠️ تعذر حذف الملف المؤقت: {file_path} | {e}")
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" not in request.files:
            return "📁 لم يتم إرفاق أي ملف.", 400

        file = request.files["file"]
        if file.filename == "":
            return "📁 اسم الملف فارغ.", 400

        if not allowed_file(file.filename):
            return "🚫 نوع الملف غير مدعوم. المسموح: PDF, JPG, PNG", 400

        # 🔒 تأمين الاسم وإضافة معرف فريد
        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4()}_{filename}"
        input_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(input_path)

        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        output_path = os.path.join(app.config["COMPRESSED_FOLDER"], f"compressed_{unique_name}")
        # تسجيل الملفات للحذف التلقائي بعد الإرسال
        g.files_to_cleanup = list({input_path, output_path})

        if ext == ".pdf":
            if not compress_pdf(input_path, output_path):
                logger.warning("⚠️ فشل ضغط PDF، سيتم إرسال الملف الأصلي.")
                output_path = input_path

        elif ext in [".jpg", ".jpeg"]:
            try:
                with Image.open(input_path) as img:
                    # تحويل لـ RGB لتجنب أخطاء قنوات الشفافية في JPEG
                    img.convert("RGB").save(
                        output_path, "JPEG", quality=60, optimize=True, progressive=True
                    )
            except Exception as e:
                logger.error(f"❌ خطأ في ضغط الصورة: {e}")
                output_path = input_path

        elif ext == ".png":
            try:
                with Image.open(input_path) as img:
                    img.save(output_path, "PNG", optimize=True, compress_level=9)
            except Exception as e:
                logger.error(f"❌ خطأ في ضغط الصورة: {e}")
                output_path = input_path

        # 📤 إرسال الملف مع اسم واضح للتحميل
        download_name = f"compressed_{filename}"
        return send_file(output_path, as_attachment=True, download_name=download_name)

    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # 🔒 إيقاف debug في الإنتاج لأسباب أمنية
    app.run(host="0.0.0.0", port=port, debug=False)