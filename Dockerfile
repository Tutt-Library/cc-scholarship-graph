# Dockerfile for Colorado College Scholarship Knowledge Graph
FROM tuttlibrary/python-base
MAINTAINER Jeremy Nelson <jermnelson@gmail.com>

# Environmental variables
ENV HOME /opt/cc-scholarship-graph
 
RUN mkdir $HOME && cd $HOME && mkdir instance && \
    touch __init__.py

COPY scholarship_graph $HOME/scholarship_graph/
COPY run.py $HOME/.
COPY instance/config.py $HOME/instance/config.py

EXPOSE 7225
WORKDIR $HOME
CMD ["nohup", "gunicorn", "-b", "0.0.0.0:7225", "run:parent_app"]

