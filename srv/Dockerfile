FROM python:3.12-alpine

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt --no-cache-dir

COPY server.py server.py
CMD ["python", "server.py"]
