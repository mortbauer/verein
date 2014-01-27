# -*- coding: utf-8 -*-

from wsgi import create_app
from flask.ext.script import Manager
from bson.objectid import ObjectId
import hashlib

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


@manager.command
def create_user(username='martin',password='martin',roles=['admin']):
    userhash = hashlib.sha1()
    encryptpass = app.bcrypt.generate_password_hash(password)
    encrypted_password = unicode(encryptpass)
    userhash.update(username)
    if app.db.users.find_one({'username':username}):
        raise Exception('username {0} already existing'.format(username))
    app.db.users.insert({
        'username':username,
        'password':encrypted_password,
        'roles':roles,
        'user_id':userhash.hexdigest(),
    })

@manager.command
def delete_user(username='martin'):
    app.db.users.remove({'username':username})

if __name__ == "__main__":
    manager.run()
