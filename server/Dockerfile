FROM python:3.12-alpine

COPY requirements.txt requirements.txt
RUN pip install -yr requirements.txt

COPY server.py server.py
CMD python server.py
