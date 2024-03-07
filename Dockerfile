FROM python:3.10-alpine

COPY . /src

WORKDIR /src

RUN apk update && apk add libxml2-dev libxslt-dev
RUN pip3 install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "python3", "main.py" ]
