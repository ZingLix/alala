FROM python:latest
RUN pip install flask requests kuriyama pymongo pyyaml flask-cors flask-login
WORKDIR /project
COPY src /project
CMD ["sh", "start.sh"]