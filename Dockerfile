# Dockerfile for Colorado College Scholarship Knowledge Graph
FROM tuttlibrary/python-base
MAINTAINER Jeremy Nelson <jermnelson@gmail.com>

# Environmental variables
ENV HOME /opt/cc-scholarship-graph
 
RUN git clone https://github.com/Tutt-Library/cc-scholarship-graph.git $HOME && \ 
    cd $HOME && mkdir instance && pip install bibtexparser PyGithub

COPY instance/config.py $HOME/instance/config.py

EXPOSE 7225
WORKDIR $HOME
CMD ["nohup", "gunicorn", "-b", "0.0.0.0:7225", "run:app"]

