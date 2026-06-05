import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
 

def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'si', 'on'}

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    USE_PROD_ENV = _env_bool('USE_PROD_ENV', False)
    DEBUG = _env_bool('FLASK_DEBUG', not USE_PROD_ENV)

    DATABASE_URL_DEV = os.environ.get('DATABASE_URL_DEV') or os.environ.get('DATABASE_URL') or 'postgresql://kiwi_user:kiwi_pass@db:5432/kiwi_db'
    DATABASE_URL_PROD = os.environ.get('DATABASE_URL_PROD') or os.environ.get('DATABASE_URL')

    SQLALCHEMY_DATABASE_URI = DATABASE_URL_PROD if USE_PROD_ENV and DATABASE_URL_PROD else DATABASE_URL_DEV
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALLOW_PUBLIC_REGISTER = os.environ.get('ALLOW_PUBLIC_REGISTER', 'false').lower() == 'true'
    
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', '20160'))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES_DAYS', '7'))
    )