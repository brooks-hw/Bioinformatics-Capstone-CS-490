from flask import Flask, request, render_template, send_from_directory
from bs4 import BeautifulSoup
import subprocess
import os
import shutil
import base64
from io import BytesIO
from PIL import Image

# -----------------------------------
# Flask App Initialization
# -----------------------------------
app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'fastqc_output'
STATIC_IMG_DIR = 'static/report_images'
TRIM_OUTPUT_FOLDER = 'trimmomatic_output'

for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, STATIC_IMG_DIR, TRIM_OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# -----------------------------------
# IMAGE EXTRACTION HELPER
# -----------------------------------
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
        if not src or not src.startswith("data:image/png;base64,"):
            continue

        base64_data = src.split(",")[1]
        img_data = base64.b64decode(base64_data)

        try:
            with Image.open(BytesIO(img_data)) as im:
                width, height = im.size
                if width < 100 or height < 100:
                    continue

                filename = f"report_image_{counter}.png"
                out_path = os.path.join(static_dir, filename)
                im.save(out_path, format="PNG")

                image_paths.append(f"/static/report_images/{filename}")
                counter += 1
        except Exception as e:
            print(f"Skipping image due to error: {e}")

    return image_paths

# -----------------------------------
# HOME PAGE
# -----------------------------------
@app.route('/')
def home():
    return render_template("Genelytics.html", images=[])

# -----------------------------------
# RUN FASTQC 
# -----------------------------------
@app.route('/run-fastqc', methods=['POST'])
def run_fastqc():
    files = request.files.getlist('dnaFiles')
    if not files:
        return "No files uploaded!", 400

    filepaths = []
    generated_reports = []

    for file in files:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        filepaths.append(filepath)

        subprocess.run(['fastqc', filepath, '-o', OUTPUT_FOLDER], check=True)

        base_name = os.path.basename(filepath)
        report_name = base_name.replace('.fastq', '_fastqc.html').replace('.gz', '_fastqc.html')
        report_path = os.path.join(OUTPUT_FOLDER, report_name)

        if os.path.exists(report_path):
            generated_reports.append(report_name)

    if not generated_reports:
        return "No FastQC reports found!", 500

    selected_report = generated_reports[0]
    images = extract_and_copy_images(os.path.join(OUTPUT_FOLDER, selected_report))

    return render_template(
        "Genelytics.html",
        images=images,
        fastqc_reports=generated_reports,
        selected_report=selected_report
    )

@app.route('/view-report')
def view_report():
    # File selected by user from dropdown
    report_name = request.args.get('file')
    report_path = os.path.join(OUTPUT_FOLDER, report_name)

    if not os.path.exists(report_path):
        return f"Report {report_name} not found!", 404

    images = extract_and_copy_images(report_path)

    # Get all available reports again (for dropdown)
    all_reports = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('_fastqc.html')]

    return render_template(
        "Genelytics.html",
        images=images,
        fastqc_reports=all_reports,
        selected_report=report_name
    )

# -----------------------------------
# RUN TRIMMOMATIC 
# -----------------------------------
@app.route('/run-trimmomatic', methods=['POST'])
def run_trimmomatic():
    # Get all uploaded files from form input name="trimFiles"
    files = request.files.getlist('trimFiles')
    if not files:
        return "No files uploaded!", 400

    trim_logs = []

    for file in files:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        print(f"Saved file: {filepath}")

        # Define output filename
        output_file = os.path.join(
            TRIM_OUTPUT_FOLDER,
            file.filename.replace(".fastq", "_trimmed.fastq").replace(".gz", "_trimmed.fastq.gz")
        )

        try:
            trimmomatic_jar = os.path.join("tools", "trimmomatic-0.39.jar")

            cmd = [
                "java", "-jar", trimmomatic_jar,
                "SE", "-threads", "4", "-phred33",
                filepath, output_file,
                "SLIDINGWINDOW:4:20", "MINLEN:50"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            trim_logs.append(f" {file.filename} trimmed successfully\n{result.stdout}\n")

        except subprocess.CalledProcessError as e:
            trim_logs.append(f"Error processing {file.filename}:\n{e.stderr}\n")

    trim_summary = "\n".join(trim_logs)
    return render_template("Genelytics.html", images=[], trim_summary=trim_summary)

# -----------------------------------
# APP LAUNCH
# -----------------------------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
