class Config:
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:13032002@localhost/webmonitor'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'supersecretkey'
    JWT_SECRET_KEY = 'supersecretjwtkey'
    JWT_ACCESS_TOKEN_EXPIRES = 43200  # 12 ore
