import os


class Config:
	DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
	SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
	SQLALCHEMY_TRACK_MODIFICATIONS = False


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
MAX_RETRIES = 5
MATCH_CONFIDENCE_THRESHOLD = 80
