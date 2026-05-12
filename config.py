import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu_clave_secreta_super_dificil_para_jwt_tokens'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://kiwi_user:kiwi_pass@db:5432/kiwi_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALLOW_PUBLIC_REGISTER = os.environ.get('ALLOW_PUBLIC_REGISTER', 'false').lower() == 'true'
    
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'clave_secreta_jwt_minimo_32_bytes_para_sha256'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', '30'))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES_DAYS', '7'))
    )