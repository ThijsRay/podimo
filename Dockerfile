FROM python:3.10-alpine

COPY . /src

WORKDIR /src

RUN pip3 install -r requirements.txt

ENTRYPOINT [ "python3", "main.py" ]
