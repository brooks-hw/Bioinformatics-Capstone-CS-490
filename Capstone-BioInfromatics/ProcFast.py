from flask import Flask, request, jsonify, send_from_directory
import subprocess
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'fastqc_output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@app.route('/')
def serve_html():
    return send_from_directory('.', 'Genelytics.html')  # Serves your HTML file


@app.route('/run-fastqc', methods=['POST'])
def run_fastqc():
    file = request.files['dnaFile']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    try:
        subprocess.run([
            'fastqc', filepath,
            '-o', OUTPUT_FOLDER
        ], check=True)

        # Read FastQC summary file (example)
        summary_path = os.path.join(OUTPUT_FOLDER, file.filename.replace('.gz', '').replace('.fastq', '') + '_fastqc', 'summary.txt')
        with open(summary_path, 'r') as f:
            summary = f.read()

        return summary
    except Exception as e:
        return f"Error running FastQC: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'fastqc_output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/run-fastqc', methods=['POST'])
def run_fastqc():
    file = request.files['dnaFile']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    try:
        subprocess.run([
            'fastqc', filepath,
            '-o', OUTPUT_FOLDER
        ], check=True)

        # Read FastQC summary file (example)
        summary_path = os.path.join(OUTPUT_FOLDER, file.filename.replace('.gz', '').replace('.fastq', '') + '_fastqc', 'summary.txt')
        with open(summary_path, 'r') as f:
            summary = f.read()

        return summary
    except Exception as e:
        return f"Error running FastQC: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
