# -*- coding: utf-8 -*-

from wsgi import create_app
from flask.ext.script import Manager
from bson.objectid import ObjectId

app = create_app()
manager = Manager(app)

@manager.shell
def make_shell_context():
    return dict(app=app, ObjectId=ObjectId)

@manager.command
def run():
    """Run in local machine."""
    app.run(host='localhost',debug=True)

@manager.command
def create_user(name='martin',password='martin',roles=['admin']):
    from wsgi.extensions import mongo
    mongo.db.users.remove({'username':name})
    if mongo.db.users.find_one({'username':name}):
        raise Exception('username {0} already existing'.format(name))
    mongo.db.users.insert({'username':name,'password':password,'roles':roles})

@manager.command
def create_test_article():
    from wsgi.extensions import mongo
    from wsgi.utils import calc_hash
    article = {
        'title':'hallo martin, neuer test',
        'tags':['test','hallo'],
        'categories':['development'],
        'short':'nur ein blöder test article',
        'content':{'rst':TEST_ARTICLE},
    }
    post = {
        '_edited':{'date':'02.12.2013','user':'martin'},
        '_etag':calc_hash(article),
        '_post':article,
        '_slug':'testpost',
    }
    mongo.db.articles.insert(post)


if __name__ == "__main__":
    manager.run()
