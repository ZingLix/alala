from Util.config import config
from api import app
import threading
from qqbot import bili_monitor, start_qqbot_loop
from rule import init
import logging
from gevent.pywsgi import WSGIServer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)


def run_flask():
    server = WSGIServer(("", config["api"]["port"]), app, log=app.logger)
    server.serve_forever()


if __name__ == "__main__":
    init()
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=bili_monitor, daemon=True).start()
    start_qqbot_loop()
    threading.Event().wait()
