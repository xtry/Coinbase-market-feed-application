FROM python:3.11-slim

WORKDIR /mock_app

COPY . /mock_app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "mockserver.py"]
