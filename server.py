# -*- coding: utf-8 -*-
from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop
from tornado.web import FallbackHandler, RequestHandler, Application
from tornado.httpserver import HTTPServer
from wsgi import create_app


class MainHandler(RequestHandler):
    def get(self):
        self.write("This message comes from Tornado ^_^")

app = create_app()
tr = WSGIContainer(app)

application = Application([
    (r"/tornado", MainHandler),
    (r".*", FallbackHandler, dict(fallback=tr)),
])
#http_server = HTTPServer(application, ssl_options={'certfile': 'self-ssl.crt', 'keyfile': 'self-ssl.key'})

if __name__ == "__main__":
    #http_server.listen(5000, address='0.0.0.0')
    application.listen(5000, address='0.0.0.0')
    IOLoop.instance().start()
