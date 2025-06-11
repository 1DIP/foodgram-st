FROM python:3.12

WORKDIR /app

RUN pip install gunicorn==20.1.0

COPY requirements.txt .

RUN pip3 install -r requirements.txt --no-cache-dir

COPY . .

CMD ["gunicorn", "foodgram.wsgi", "--bind", "0:8000"]