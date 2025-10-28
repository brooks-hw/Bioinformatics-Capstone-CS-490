FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    openjdk-11-jre-headless \
    fastqc \
    wget \
    unzip \
    perl \
    build-essential \
    samtools \
    jellyfish \
    bowtie2 \
    salmon \
    bwa \
    && rm -rf /var/lib/apt/lists/*

# Install Python and pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

# Copy your requirements file (from your project directory)
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Install Trimmomatic (official UsadelLab source)
WORKDIR /opt/tools
RUN wget http://www.usadellab.org/cms/uploads/supplementary/Trimmomatic/Trimmomatic-0.39.zip \
    && unzip Trimmomatic-0.39.zip \
    && rm Trimmomatic-0.39.zip
ENV TRIMMOMATIC_JAR=/opt/tools/Trimmomatic-0.39/trimmomatic-0.39.jar

# Install Trinity
RUN wget https://github.com/trinityrnaseq/trinityrnaseq/releases/download/Trinity-v2.15.1/trinityrnaseq-v2.15.1.FULL.tar.gz \
    && tar -xvzf trinityrnaseq-v2.15.1.FULL.tar.gz \
    && mv trinityrnaseq-v2.15.1 /opt/tools/trinityrnaseq \
    && rm trinityrnaseq-v2.15.1.FULL.tar.gz
ENV PATH=$PATH:/opt/tools/trinityrnaseq

# Tell Trinity where dependency binaries are
ENV TRINITY_HOME=/opt/tools/trinityrnaseq
ENV PATH=$PATH:/usr/bin:/opt/tools/trinityrnaseq

WORKDIR /workspace
ENTRYPOINT ["/bin/bash"]