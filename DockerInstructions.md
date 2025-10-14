**The following are instructions to create the project container with Docker and enter the development environment**

1. Download Docker desktop and ensure that it's running in the background
2. Clone or pull the current version of the repository from the github
3. Enter the main project directory containing 'Dockerfile' from the command line
4. Build the container:
   - **Run:** docker build -t capstone-pipeline .
5. Enter the envrionment:
   - **Run:** docker run --rm -it -v $PWD:/workspace capstone-pipeline
   - rm: ensures cleanup after exiting
   - it: starts the environment in an interactive shell
   - -v $PWD:/workspace 
6. Once inside the container, you may check to see if installations were successful:
   - fastqc --version
   - java -jar $TRIMMOMATIC_JAR -version
   - Trinity --version
   - samtools --version | head -n1 
   - python3 --version
7. Leave the container environment at any time by typing 'exit'