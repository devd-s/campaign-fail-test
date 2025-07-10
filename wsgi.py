import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app import app

if __name__ == "__main__":
    app.run()
