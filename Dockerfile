FROM python:3.9.5-slim
RUN pip install flask requests kuriyama pymongo pyyaml flask-cors flask-login
WORKDIR /project
COPY src /project
CMD ["sh", "start.sh"]