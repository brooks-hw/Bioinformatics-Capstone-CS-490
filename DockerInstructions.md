**The following are instructions to create the project container with Docker and enter the development environment**

1. Download Docker desktop and ensure that it's running in the background
2. Clone or pull the current version of the repository from the github
3. Enter the main project directory containing 'Dockerfile' from the command line
**The following step can be completed 1 of 2 ways**
4. Build the container locally (recommended if new tools/librarires are added):
   - **Run:** docker build -t capstone-pipeline .
5. Pull the pre-built container from Docker hub
   - **Run:** 
7. Enter the envrionment:
   - **Run:** (Linux) docker run --rm -it -v $PWD:/workspace capstone-pipeline
              (Windows) docker run --rm -it -v "%cd%":/workspace capstone-pipeline
   - rm: ensures cleanup after exiting
   - it: starts the environment in an interactive shell
   - -v $PWD:/workspace 
8. Once inside the container, you may check to see if installations were successful:
   - fastqc --version
   - java -jar $TRIMMOMATIC_JAR -version
   - Trinity --version
   - samtools --version | head -n1 
   - python3 --version
9. Leave the container environment at any time by typing 'exit'
