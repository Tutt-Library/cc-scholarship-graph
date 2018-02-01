# Dockerfile for Colorado College Scholarship Knowledge Graph
FROM python:3.6.4 
MAINTAINER: Jeremy Nelson <jermnelson@gmail.com>

# Environmental variables
ENV HOME /opt/cc-scholarship-graph

RUN apt-get update && apt-get install -y && \
    mkdir $HOME && cd $HOME && mkdir instance

COPY scholarship_graph $HOME
COPY requirements.txt $HOME
COPY instance/config.py $HOME/instance/config.py

RUN cd $HOME && python -r requirements.txt && \
    
EXPOSE 7225
WORKDIR $HOME
CMD ["nohup", "gunicorn", "-b", "0.0.0.0:7225", "scholarship_graph/app:app"]

