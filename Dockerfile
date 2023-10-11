FROM python:3.10-alpine

WORKDIR /src

COPY requirements.txt /src/
RUN apk add libxml2-dev libxslt-dev gcc libc-dev && pip3 install --no-cache-dir -r requirements.txt

COPY . /src

ENTRYPOINT [ "python3", "main.py" ]
