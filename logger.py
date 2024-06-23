import logging
import os
from datetime import date

class Logger:
    _instance = None

    @staticmethod
    def getInstance():
        if Logger._instance is None:
            Logger()
        return Logger._instance

    def __init__(self):
        if Logger._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Logger._instance = self
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)

            log_dir = 'log'
            try:
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
            except Exception as e:
                raise Exception(f"Failed to create log directory: {e}")

            log_file = f'{log_dir}/{date.today()}.log'
            try:
                handler = logging.FileHandler(log_file)
            except Exception as e:
                raise Exception(f"Failed to create log file: {e}")

            handler.setLevel(logging.INFO)

            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)

            self.logger.addHandler(handler)

    def log(self, message):
        print(f"Logging message: {message}")  # Debug print
        try:
            self.logger.info(message)
        except Exception as e:
            print(f"Failed to write to log file: {e}")  # Debug print