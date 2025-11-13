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
TRINITY_OUTPUT_FOLDER = 'trinity_output' 
DOWNLOAD_FOLDER = 'static/downloads' 

# create folders if they don't exist
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, STATIC_IMG_DIR, TRIM_OUTPUT_FOLDER, TRINITY_OUTPUT_FOLDER, DOWNLOAD_FOLDER]:
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
    download_links = []

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
        
            download_url = f"/downloads/{os.path.basename(report_path)}"
            shutil.copy(report_path, os.path.join("static/downloads", os.path.basename(report_path)))
            download_links.append((os.path.basename(report_path), download_url))


    if not generated_reports:
        return "No FastQC reports found!", 500

    selected_report = generated_reports[0]
    images = extract_and_copy_images(os.path.join(OUTPUT_FOLDER, selected_report))

    return render_template(
        "Genelytics.html",
        images=images,
        fastqc_reports=generated_reports,
        selected_report=selected_report,
        download_links=download_links
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
        selected_report=report_name,
    )

# -----------------------------------
# RUN TRIMMOMATIC 
# -----------------------------------
@app.route('/run-trimmomatic', methods=['POST'])
def run_trimmomatic():
    mode = request.form.get("mode", "SE")
    threads = request.form.get("threads", "4")
    phred = request.form.get("phred", "-phred33")
    steps = request.form.getlist("steps")  # list of selected trimming steps

    # Get all uploaded files from form input name="trimFiles"
    files = request.files.getlist('trimFiles')
    if not files:
        return "No files uploaded!", 400

    trim_logs = []
    download_links = []

    for file in files:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        print(f"Saved file: {filepath}")

        output_filename = file.filename.replace(".fastq", "_trimmed.fastq").replace(".gz", "_trimmed.fastq.gz")
        output_file = os.path.join(TRIM_OUTPUT_FOLDER, output_filename)


        try:
            trimmomatic_jar = os.path.join("tools", "trimmomatic-0.39.jar")

            cmd = [
                "java", "-jar", trimmomatic_jar,
                mode, "-threads", threads, phred,
                filepath, output_file
            ] + steps


            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            trim_logs.append(f" {file.filename} trimmed successfully\n{result.stdout}\n")

            
            download_url = f"/downloads/{output_filename}"
            shutil.copy(output_file, os.path.join("static/downloads", output_filename))
            download_links.append((output_filename, download_url))


        except subprocess.CalledProcessError as e:
            trim_logs.append(f"Error processing {file.filename}:\n{e.stderr}\n")

    trim_summary = "\n".join(trim_logs)
    return render_template(
        "Genelytics.html", 
        images=[],
        trim_summary=trim_summary,
        download_links=download_links
    )

# -----------------------------------
# RUN TRINITY
# -----------------------------------
@app.route('/run-trinity', methods=['POST'])
def run_trinity():
    # Get uploaded file(s) from the form (HTML input name="trinityFiles")
    files = request.files.getlist('trinityFiles')
    if not files:
        return "No file uploaded!", 400

    #find file path of uploaded file
    saved_paths = []
    for f in files:
        filepath = os.path.join(UPLOAD_FOLDER, f.filename)
        f.save(filepath)

        if os.path.getsize(filepath) == 0:
            return "Uploaded FASTQ file is empty. Please provide a valid file.", 400


        saved_paths.append(filepath)

    # Ensure Trinity output directory exists
    os.makedirs(TRINITY_OUTPUT_FOLDER, exist_ok=True)
    output_dir = os.path.join(TRINITY_OUTPUT_FOLDER, "trinity_assembly")

    # Remove any previous output (optional, keeps directory clean)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Build the Trinity command (default settings)
    cmd = [
        "Trinity",
        "--seqType", "fq",
        "--single", ",".join(saved_paths), #multiple files supported //#input_path,
        "--CPU", "4",
        "--max_memory", "8G",
        "--output", output_dir
    ]

    # Prepare a short summary
    #trinity_summary = f"Running Trinity on {uploaded_file.filename}\n\nCommand:\n{' '.join(cmd)}\n\n"
    trinity_summary = f"Running Trinity on {', '.join([f.filename for f in files])}\n\nCommand:\n{' '.join(cmd)}\n\n"
    download_links = [] #initialize download links

    try:
        # Run Trinity
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        trinity_summary += "Trinity completed successfully.\n\n"
        trinity_summary += f"Output saved in: {output_dir}\n\n"
        trinity_summary += f"Trinity Log (first 1000 chars):\n{result.stdout[:1000]}"

        
        # Identify main output file (usually 'Trinity.fasta')
        output_filename = "Trinity.fasta"
        output_file_path = os.path.join(output_dir, output_filename)

        if os.path.exists(output_file_path):
            download_url = f"/downloads/{output_filename}"
            shutil.copy(output_file_path, os.path.join("static/downloads", output_filename))
            download_links.append((output_filename, download_url))


    except subprocess.CalledProcessError as e:
        print("=== TRINITY ERROR ===")
        print(e.stderr)
        print("=====================")
        trinity_summary += f" Trinity failed.\n\nError log (first 1000 chars):\n{e.stderr[:1000]}"
    finally:   
    # Safe cleanup for all uploaded files
        for path in saved_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except PermissionError:
                print(f"Could not delete {path} due to permission issues.")


    # Render page with results
    return render_template(
        "Genelytics.html",
        trinity_summary=trinity_summary,
        images=[],
        download_links=download_links
    )
# -----------------------------------
# RUN BURROWS–WHEELER (BWA + SAMTOOLS)
# -----------------------------------
@app.route('/run-bwt', methods=['POST'])
def run_bwt():
    # Get uploaded files from form (HTML input name="bwtFiles")
    files = request.files.getlist('bwtFiles')
    if len(files) < 2:
        return "Please upload both FASTQ reads and reference FASTA file.", 400

    # Separate FASTQ and reference FASTA
    fastq_file = None
    reference_file = None
    for f in files:
        if f.filename.endswith(('.fa', '.fasta')):
            reference_file = f
        elif f.filename.endswith(('.fq', '.fastq', '.gz')):
            fastq_file = f

    if not fastq_file or not reference_file:
        return "Missing required FASTQ or reference FASTA file.", 400

    # Save input files locally
    fastq_path = os.path.join("uploads", fastq_file.filename)
    ref_path = os.path.join("uploads", reference_file.filename)
    fastq_file.save(fastq_path)
    reference_file.save(ref_path)

    # Ensure output directory exists
    BWT_OUTPUT_FOLDER = "bwt_output"
    os.makedirs(BWT_OUTPUT_FOLDER, exist_ok=True)

    # Paths for generated files
    sam_path = os.path.join(BWT_OUTPUT_FOLDER, "alignment.sam")
    bam_path = os.path.join(BWT_OUTPUT_FOLDER, "alignment.bam")
    sorted_bam = os.path.join(BWT_OUTPUT_FOLDER, "alignment_sorted.bam")

    # Optional SAMtools flag (add a checkbox named "run_samtools" in HTML)
    run_samtools = request.form.get("run_samtools") == "on"

    bwt_summary = f"Running Burrows–Wheeler Alignment (BWA MEM)\n\n"
    bwt_summary += f"Reference: {reference_file.filename}\nReads: {fastq_file.filename}\n\n"

    download_links = []

    try:
        # Step 1: Index the reference
        index_cmd = ["bwa", "index", ref_path]
        subprocess.run(index_cmd, check=True, capture_output=True, text=True)
        bwt_summary += f"Indexed reference with command:\n{' '.join(index_cmd)}\n\n"

        # Step 2: Run alignment
        align_cmd = ["bwa", "mem", ref_path, fastq_path]
        with open(sam_path, "w") as sam_out:
            subprocess.run(align_cmd, check=True, text=True, stdout=sam_out)
        bwt_summary += f"Alignment completed using command:\n{' '.join(align_cmd)}\n\n"

        
        # Add SAM file to download links
        shutil.copy(sam_path, os.path.join("static/downloads", "alignment.sam"))
        download_links.append(("alignment.sam", "/downloads/alignment.sam"))


        # Step 3 (optional): SAMtools conversion + sorting + indexing
        if run_samtools:
            bwt_summary += "Running SAMtools steps (convert → sort → index)...\n\n"

            convert_cmd = ["samtools", "view", "-S", "-b", sam_path, "-o", bam_path]
            subprocess.run(convert_cmd, check=True, capture_output=True, text=True)

            sort_cmd = ["samtools", "sort", bam_path, "-o", sorted_bam]
            subprocess.run(sort_cmd, check=True, capture_output=True, text=True)

            index_cmd = ["samtools", "index", sorted_bam]
            subprocess.run(index_cmd, check=True, capture_output=True, text=True)

            bwt_summary += f"Generated sorted and indexed BAM file:\n{sorted_bam}\n\n"

            
            # Add BAM files to download links
            shutil.copy(sorted_bam, os.path.join("static/downloads", "alignment_sorted.bam"))
            download_links.append(("alignment_sorted.bam", "/downloads/alignment_sorted.bam"))

        else:
            bwt_summary += "SAMtools skipped (only SAM file generated).\n\n"

        bwt_summary += f"All output files are in: {BWT_OUTPUT_FOLDER}\n"

    except subprocess.CalledProcessError as e:
        bwt_summary += f"\nError running Burrows–Wheeler or SAMtools:\n{e.stderr[:1000]}"

    finally:
        # Cleanup temporary uploaded input files
        if os.path.exists(fastq_path):
            os.remove(fastq_path)
        if os.path.exists(ref_path):
            os.remove(ref_path)

    return render_template(
        "Genelytics.html",
        bwt_summary=bwt_summary,
        images=[],
        download_links=download_links
    )

@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_from_directory('static/downloads', filename, as_attachment=True)

# -----------------------------------
# APP LAUNCH
# -----------------------------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
