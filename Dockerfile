FROM python:3.9.5-slim
RUN pip install flask requests kuriyama pymongo pyyaml flask-cors flask-login gevent websocket-client
WORKDIR /project
COPY src /project
CMD ["python", "main.py"]