
from pymongo import MongoClient
from gridfs import GridFS

class Mongo(object):
    def __init__(self,app=None):
        if app:
            self.init_app(app)

    def init_app(self,app):
        kwargs = {'host':app.config['MONGO_HOST'],
            'port':app.config['MONGO_PORT'],
            'username':app.config.get('MONGO_USERNAME'),
            'password':app.config.get('MONGO_PASSWORD')}
        if kwargs['username'] and kwargs['password']:
            user = '{d[username]}:{d[password]}@'.format(d=kwargs)
        else:
            user = ''
        host = '{d[host]}:{d[port]}'.format(d=kwargs)
        fulluri = 'mongodb://{user}{host}'.format(user=user,host=host)
        self.connection = MongoClient(fulluri)
        self.db = self.connection[app.config['MONGO_DBNAME']]
        self.fs = GridFS(self.db)
