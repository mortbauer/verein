import os

MONGO_HOST = os.environ['OPENSHIFT_MONGODB_DB_HOST']
MONGO_PORT = int(os.environ['OPENSHIFT_MONGODB_DB_PORT'])
MONGO_USERNAME = 'admin'
MONGO_PASSWORD = 'xzIzWL9NZd-I'
TMP = os.environ['OPENSHIFT_TMP_DIR']
SERVER_NAME = 'verein-mortbauer.rhcloud.com'
