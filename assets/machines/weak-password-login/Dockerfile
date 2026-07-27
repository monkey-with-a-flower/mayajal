FROM python:3.12-alpine

WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3
COPY app.py /app/app.py

ENV FLASK_APP=app.py
EXPOSE 8080
CMD ["python", "/app/app.py"]
