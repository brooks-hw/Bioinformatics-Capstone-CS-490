from flask import Flask, request, render_template, send_from_directory
from bs4 import BeautifulSoup
import subprocess
import os
import shutil
import base64

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'fastqc_output'
STATIC_IMG_DIR = 'static/report_images'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(STATIC_IMG_DIR, exist_ok=True)

# -------------------------------
# GRABBING IMAGES!
# -------------------------------
def extract_and_copy_images(report_path, static_dir="static/report_images"):
    os.makedirs(static_dir, exist_ok=True)

    # Clear old images
    for f in os.listdir(static_dir):
        os.remove(os.path.join(static_dir, f))

    with open(report_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    main_div = soup.find("div", class_="main")
    if not main_div:
        return []

    image_paths = []
    counter = 1
    for img in main_div.find_all("img"):
        src = img.get("src")
        if src and src.startswith("data:image/png;base64,"):
            base64_data = src.split(",")[1]
            img_data = base64.b64decode(base64_data)

            filename = f"report_image_{counter}.png"
            out_path = os.path.join(static_dir, filename)
            with open(out_path, "wb") as out:
                out.write(img_data)

            image_paths.append(f"/static/report_images/{filename}")
            counter += 1

    return image_paths


# ----------------
# Main page ^_^
# ----------------
@app.route('/')
def home():
    return render_template("Genelytics.html", images=[])

@app.route('/run-fastqc', methods=['POST'])
def run_fastqc():
    file = request.files['dnaFile']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    try:
        subprocess.run(['fastqc', filepath, '-o', OUTPUT_FOLDER], check=True)
        report_html = os.path.join(OUTPUT_FOLDER, 'example_fastqc.html')
        if not os.path.exists(report_html):
            return "FastQC report not found!", 500

        images = extract_and_copy_images(report_html)
        return render_template("Genelytics.html", images=images)

    except Exception as e:
        return f"Error running FastQC: {str(e)}", 500

#-------------------------
#Application Launch Point!
#-------------------------
if __name__ == '__main__':
    app.run(debug=True)
