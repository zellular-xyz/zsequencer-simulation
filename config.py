from dotenv import load_dotenv
import os

load_dotenv()

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(ROOT_DIR, "tmp_dir")

ZSEQUENCER_PROJECT_ROOT = os.getenv("ZSEQUENCER_PROJECT_ROOT")
ZSEQUENCER_PROJECT_VIRTUAL_ENV = os.getenv("ZSEQUENCER_PROJECT_VIRTUAL_ENV")
