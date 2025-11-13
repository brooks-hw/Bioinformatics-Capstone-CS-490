FROM ubuntu:22.04

# Core system dependencies
RUN apt-get update && apt-get install -y \
    openjdk-11-jre-headless \
    wget \
    unzip \
    perl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && rm /tmp/miniconda.sh
ENV PATH=/opt/conda/bin:$PATH

# Install required bioinformatics tools in one conda environment
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    conda create -y -n genelytics_env -c bioconda -c conda-forge \
    trinity fastqc trimmomatic samtools jellyfish bowtie2 salmon bwa && \
    echo "conda activate genelytics_env" >> ~/.bashrc
ENV PATH=/opt/conda/envs/genelytics_env/bin:$PATH

# Install Python requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Working directory
WORKDIR /workspace
ENTRYPOINT ["/bin/bash"]