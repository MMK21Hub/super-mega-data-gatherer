from os import getenv
from dotenv import load_dotenv

load_dotenv()


def get_env_or_raise(key: str) -> str:
    value = getenv(key)
    if not value:
        raise ValueError(f"{key} environment variable is not set")
    return value
