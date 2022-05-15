FROM python:alpine

COPY . /src

WORKDIR /src

RUN pip3 install -r requirements.txt

ENTRYPOINT [ "/src/entrypoint.sh" ]