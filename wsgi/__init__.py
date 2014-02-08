from flask import Flask


def create_app():
    # create app with the name of the package
    app = Flask(__name__,template_folder='templates', static_folder='static')
    # configure from config file
    app.config.from_object('%s.config'%__name__)
    app.config.from_pyfile('production.py', silent=True)
    # configure extensions
    configure_extensions(app)
    # configure blueprints
    configure_blueprints(app)
    return app

def configure_blueprints(app):
    from .api import accounting
    app.register_blueprint(accounting.mod)
    from . import login
    app.register_blueprint(login.mod)

def configure_extensions(app):
    from . mongo import Mongo
    mongo = Mongo(app)
    app.db = mongo.db.mortbauer
    from . mongosession import MongoSessionInterface
    app.session_interface = MongoSessionInterface(db=app.config['MONGO_DBNAME'])
    from flask.ext.bcrypt import Bcrypt
    app.bcrypt = Bcrypt(app)
