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

# create folders if they don't exist
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, STATIC_IMG_DIR, TRIM_OUTPUT_FOLDER, TRINITY_OUTPUT_FOLDER]:
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
    mode = request.form.get("mode", "SE")
    threads = request.form.get("threads", "4")
    phred = request.form.get("phred", "-phred33")
    steps = []

    if request.form.get("sliding") == "on":
        win = request.form.get("sliding_window")
        qual = request.form.get("sliding_quality")
        steps.append(f"SLIDINGWINDOW:{win}:{qual}")

    if request.form.get("minlen") == "on":
        val = request.form.get("minlen_val")
        steps.append(f"MINLEN:{val}")

    if request.form.get("crop") == "on":
        val = request.form.get("crop_val")
        steps.append(f"CROP:{val}")

    if request.form.get("headcrop") == "on":
        val = request.form.get("headcrop_val")
        steps.append(f"HEADCROP:{val}")

    files = request.files.getlist('trimFiles')
    if not files:
        return "No files uploaded!", 400

    trim_logs = []

    for file in files:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        print(f"Saved file: {filepath}")

        # Define output and log paths
        output_file = os.path.join(
            TRIM_OUTPUT_FOLDER,
            file.filename.replace(".fastq", "_trimmed.fastq").replace(".gz", "_trimmed.fastq.gz")
        )
        trim_log_path = os.path.join(TRIM_OUTPUT_FOLDER, f"{file.filename}_trimlog.txt")

        try:
            trimmomatic_jar = os.path.join("tools", "trimmomatic-0.39.jar")

            cmd = [
                "java", "-jar", trimmomatic_jar,
                mode, "-threads", threads, phred,
                filepath, output_file
            ] + steps + [f"-trimlog", trim_log_path]

            print("Running:", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Trimmomatic usually writes its summary to STDERR, not STDOUT
            combined_output = (result.stdout or "") + "\n" + (result.stderr or "")

            summary_line = None

            # Look for a summary line in combined output
            for line in combined_output.splitlines():
                if any(x in line for x in ["Input Read", "Input Reads", "Both Surviving", "Surviving:", "Dropped:"]):
                    summary_line = line.strip()
                    break

            # If not found, look in the trimlog file as a fallback
            if not summary_line and os.path.exists(trim_log_path):
                with open(trim_log_path, "r") as log:
                    for l in log:
                        if any(x in l for x in ["Input Read", "Input Reads", "Both Surviving", "Surviving:", "Dropped:"]):
                            summary_line = l.strip()
                            break

            # Build clean result message for this file
            if summary_line:
                trim_logs.append(f"{file.filename} trimmed successfully.\n{summary_line}\n")
            else:
                trim_logs.append(f"{file.filename} trimmed successfully.\nNo trimming summary detected.\n")

        except subprocess.CalledProcessError as e:
            err = e.stderr[:800] if e.stderr else "Unknown error"
            trim_logs.append(f"Error processing {file.filename}:\n{err}\n")

    trim_summary = "\n".join(trim_logs)
    return render_template("Genelytics.html", images=[], trim_summary=trim_summary)

# -----------------------------------
# RUN TRINITY
# -----------------------------------
@app.route('/run-trinity', methods=['POST'])
def run_trinity():
    # Get uploaded file(s) from the form (HTML input name="trinityFiles")
    files = request.files.getlist('trinityFiles')
    if not files:
        return "No file uploaded!", 400

    # We’ll just use the first uploaded file for this run
    uploaded_file = files[0]

    # Save it temporarily to the current working directory
    input_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
    uploaded_file.save(input_path)

    output_dir = TRINITY_OUTPUT_FOLDER
    os.makedirs(output_dir, exist_ok=True)

    # Remove any previous output (optional, keeps directory clean)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Build the Trinity command (default settings)
    cmd = [
        "Trinity",
        "--seqType", "fq",
        "--single", input_path,
        "--CPU", "4",
        "--max_memory", "8G",
        "--output", output_dir
    ]

    # Prepare a short summary
    trinity_summary = f"Running Trinity on {uploaded_file.filename}\n\nCommand:\n{' '.join(cmd)}\n\n"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        success = True

        trinity_summary += "Trinity completed successfully.\n\n"
        trinity_summary += f"Output saved in: {output_dir}\n\n"
        trinity_summary += f"Trinity Log (first 1000 chars):\n{result.stdout[:1000]}"

    except subprocess.CalledProcessError as e:
        success = False

        trinity_summary += f" Trinity failed.\n\nError log (first 1000 chars):\n{e.stderr[:1000]}"

    finally:
        # Clean up temporary uploaded FASTQ file
        #if os.path.exists(input_path):
        #    os.remove(input_path)
        pass

    # Render page with results
    return render_template(
        "Genelytics.html",
        trinity_summary=trinity_summary,
        trinity_success=success,
        images=[]
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
        else:
            bwt_summary += "SAMtools skipped (only SAM file generated).\n\n"

        bwt_summary += f"All output files are in: {BWT_OUTPUT_FOLDER}\n"

    except subprocess.CalledProcessError as e:
        bwt_summary += f"\nError running Burrows–Wheeler or SAMtools:\n{e.stderr[:1000]}"
    finally:
        pass
        # Cleanup temporary uploaded input files
        #if os.path.exists(fastq_path):
        #    os.remove(fastq_path)
        #if os.path.exists(ref_path):
        #    os.remove(ref_path)

    return render_template(
        "Genelytics.html",
        bwt_summary=bwt_summary,
        images=[]
    )


# -----------------------------------
# RUN DESEQ2 Differential Expression
# -----------------------------------
@app.route('/run-deseq2', methods=['POST'])
def run_deseq2():

    # Input files selected by <input type="file" name="deseqFiles">
    files = request.files.getlist('deseqFiles')
    if len(files) < 2:
        return "Upload count_matrix.csv AND conditions.csv", 400

    # Separate files by extension
    count_matrix = None
    conditions = None
    for f in files:
        if "count" in f.filename.lower():
            count_matrix = f
        elif "condition" in f.filename.lower() or "meta" in f.filename.lower():
            conditions = f

    if not count_matrix or not conditions:
        return "Files not recognized — name them as *count* and *condition*", 400

    # Save uploaded files
    os.makedirs("deseq2_input", exist_ok=True)
    count_path = os.path.join("deseq2_input", count_matrix.filename)
    cond_path = os.path.join("deseq2_input", conditions.filename)
    count_matrix.save(count_path)
    conditions.save(cond_path)

    # Output directory
    outdir = "deseq2_output"
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)

    # Call DESeq2 through Rscript
    deseq_script = "deseq_run.R"  
    cmd = ["Rscript", deseq_script, count_path, cond_path, outdir]

    deseq_summary = f"Running DESeq2\nCommand:\n{' '.join(cmd)}\n\n"

    try:
        result = subprocess.run(cmd, text=True, capture_output=True, check=True)
        deseq_summary += "DESeq2 completed successfully!\n\n"
        deseq_summary += "Results saved in deseq2_output/\n\n"
        deseq_summary += "R Log (first 1000 chars):\n" + result.stdout[:1000]

    except subprocess.CalledProcessError as e:
        deseq_summary += "DESeq2 FAILED ❌\n\n"
        deseq_summary += f"Return code: {e.returncode}\n\n"
        deseq_summary += "STDOUT:\n"
        deseq_summary += (e.stdout or "") + "\n\n"
        deseq_summary += "STDERR:\n"
        deseq_summary += (e.stderr or "")


    return render_template("Genelytics.html", deseq_summary=deseq_summary, images=[])



# -----------------------------------
# APP LAUNCH
# -----------------------------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)