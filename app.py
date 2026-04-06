# app.py
import os
import uuid
import shutil
import subprocess
import logging
import unicodedata
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

# إنشاء المجلدات تلقائيًا
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["COMPRESSED_FOLDER"], exist_ok=True)

# 📝 إعداد نظام السجلات (Logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    """التحقق من أن امتداد الملف مسموح"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_ghostscript_path():
    """البحث عن مسار Ghostscript بشكل متوافق مع جميع الأنظمة"""
    for cmd in ["gswin64c", "gswin32c", "gs"]:
        path = shutil.which(cmd)
        if path:
            return path
    # مسار احتياطي لويندوز (يمكن تعديله حسب إصدارك)
    fallback = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError("Ghostscript not found. Please install it and add to PATH.")


def compress_pdf(input_path, output_path):
    """ضغط ملف PDF باستخدام Ghostscript"""
    try:
        gs_path = get_ghostscript_path()
        subprocess.run([
            gs_path,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/screen",  # أقل جودة = حجم أصغر
            "-dDownsampleColorImages=true",
            "-dColorImageResolution=72",
            "-dNOPAUSE",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ], check=True, capture_output=True, text=True)
        
        logger.info(f"✅ تم ضغط PDF: {os.path.basename(input_path)}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ فشل ضغط PDF: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في ضغط PDF: {e}")
        return False


def sanitize_download_name(filename):
    """
    تنظيف اسم الملف للتحميل ليدعم المتصفحات والأحرف العربية.
    يحول الأحرف العربية لأحرف لاتينية مقاربة، أو يستخدم اسم بديل.
    """
    # محاولة تحويل الأحرف العربية لإنجليزية (Transliteration)
    normalized = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('ASCII')
    
    # إذا أصبح الاسم فارغًا (لأنه كان عربيًا بالكامل)، نستخدم اسمًا افتراضيًا
    if not normalized.strip():
        name, ext = os.path.splitext(filename)
        return f"compressed_file{ext}"
    
    return f"compressed_{normalized}"


@app.errorhandler(413)
def request_entity_too_large(error):
    """معالجة خطأ حجم الملف الكبير"""
    return "📦 حجم الملف يتجاوز 10 ميجا. يرجى اختيار ملف أصغر.", 413


@app.errorhandler(500)
def internal_error(error):
    """معالجة الأخطاء الداخلية وعرض رسالة صديقة"""
    logger.error(f"💥 Internal Server Error: {error}", exc_info=True)
    return "❌ حدث خطأ داخلي في الخادم. يرجى المحاولة لاحقًا.", 500


@app.after_request
def cleanup_temp_files(response):
    """🗑️ حذف الملفات المؤقتة بعد إرسال الاستجابة للعميل"""
    if hasattr(g, "files_to_cleanup"):
        for file_path in g.files_to_cleanup:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"🗑️ تم حذف: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ تعذر حذف الملف: {file_path} | {e}")
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            # 1. التحقق من وجود الملف
            if "file" not in request.files:
                return "📁 لم يتم إرفاق أي ملف.", 400

            file = request.files["file"]
            if file.filename == "":
                return "📁 اسم الملف فارغ.", 400

            # 2. التحقق من نوع الملف
            if not allowed_file(file.filename):
                return "🚫 نوع الملف غير مدعوم. المسموح: PDF, JPG, PNG", 400

            # 3. تجهيز المسارات
            original_filename = file.filename  # حفظ الاسم الأصلي (عربي/إنجليزي)
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower()
            
            # اسم داخلي آمن للتخزين (UUID) لتجنب مشاكل التسمية والتكرار
            safe_internal_name = f"{uuid.uuid4()}{ext}"
            
            input_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_internal_name)
            file.save(input_path)

            output_path = os.path.join(app.config["COMPRESSED_FOLDER"], f"compressed_{safe_internal_name}")
            
            # تسجيل الملفات للحذف التلقائي لاحقًا
            g.files_to_cleanup = list({input_path, output_path})

            # 4. عملية الضغط حسب النوع
            if ext == ".pdf":
                if not compress_pdf(input_path, output_path):
                    logger.warning("⚠️ فشل ضغط PDF، سيتم إرسال الملف الأصلي.")
                    output_path = input_path

            elif ext in [".jpg", ".jpeg"]:
                try:
                    with Image.open(input_path) as img:
                        # تحويل لـ RGB لتجنب أخطاء الشفافية في JPEG
                        img.convert("RGB").save(
                            output_path, "JPEG", quality=60, optimize=True, progressive=True
                        )
                except Exception as e:
                    logger.error(f"❌ خطأ في ضغط JPEG: {e}")
                    output_path = input_path

            elif ext == ".png":
                try:
                    with Image.open(input_path) as img:
                        # حفظ PNG مع ضغط عالٍ
                        img.save(output_path, "PNG", optimize=True, compress_level=9)
                except Exception as e:
                    logger.error(f"❌ خطأ في ضغط PNG: {e}")
                    output_path = input_path

            # 5. تجهيز الاسم للتحميل (Download Name)
            # نستخدم دالة التنظيف لضمان توافق الاسم مع جميع المتصفحات
            download_name = sanitize_download_name(original_filename)

            # 6. إرسال الملف
            return send_file(
                output_path,
                as_attachment=True,
                download_name=download_name  # يعمل مع Flask >= 2.0
            )

        except Exception as e:
            # تسجيل الخطأ بالتفصيل في السيرفر
            logger.error(f"💥 Unexpected Error: {type(e).__name__} - {e}", exc_info=True)
            return "❌ حدث خطأ غير متوقع أثناء معالجة الملف.", 500

    # عرض صفحة الرفع (GET request)
    return render_template("index.html")


if __name__ == "__main__":
    # تحديد المنفذ من متغيرات البيئة (مهم لـ Render/Heroku)
    port = int(os.environ.get("PORT", 5000))
    # debug=False ضروري للأمان عند النشر
    app.run(host="0.0.0.0", port=port, debug=False)