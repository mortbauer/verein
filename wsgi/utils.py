#coding=utf-8
import cerberus
from abc import ABCMeta, abstractmethod
import datetime
from bson.objectid import ObjectId
from bson.json_util import dumps
from flask import request, abort, make_response, Response
from werkzeug.exceptions import BadRequest
from types import FunctionType
from functools import wraps
import simplejson as json
from flask import jsonify
from BaseHTTPServer import BaseHTTPRequestHandler
from io import StringIO
import hashlib
import dateutil.parser

class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.rfile = StringIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message

class APIEncoder(json.JSONEncoder):
    """ Propretary JSONEconder subclass used by the json render function.
    This is needed to address the encoding of special values.
    """
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            # convert any datetime to RFC 1123 format
            return date_to_str(obj)
        elif isinstance(obj, (datetime.time, datetime.date)):
            # should not happen since the only supported date-like format
            # supported at dmain schema level is 'datetime' .
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            # BSON/Mongo ObjectId is rendered as unicode
            return str(obj)
        return json.JSONEncoder.default(self, obj)

def send_response(data, last_modified=None, etag=None,status=200, host=None):
    """ Prepares the response object according to the client request and
    available renderers, making sure that all accessory directives (caching,
    etag, last-modified) are present.

    :param data: the dict that should be sent back as a response.
    :param last_modified: Last-Modified header value.
    :param etag: ETag header value.
    :param status: response status.

    """
    if isinstance(data, Response):
        return data
    # invoke the render function and obtain the corresponding rendered item
    rendered = json.dumps(data, cls=APIEncoder)
    # build the main wsgi rensponse object
    resp = make_response(rendered, status)
    resp.mimetype = 'application/json'

    # etag and last-modified
    if etag:
        resp.headers.add('ETag', etag)
    if last_modified:
        resp.headers.add('Last-Modified', date_to_str(last_modified))
    if host:
        resp.headers.add('Host',host)

    return resp

def send(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        resp = f(*args,**kwargs)
        return send_response(resp,**kwargs)
    return wrapper

class RestException(Exception):
    """ Base Class for Restful Exceptions

    they need at least to implement the to_dict method
    to register them you need to do something like::

        @app.errorhandler(RestException)
        def handle(error):
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
    """
    __metaclass__ = ABCMeta
    @abstractmethod
    def to_dict(self):
        raise NotImplementedError

class InvalidUsage(RestException):
    status_code = 400

    def __init__(self, payload, status_code=None):
        super(self.__class__,self).__init__(self)
        self.payload = payload
        self.error = {'errors':payload}
        if status_code is not None:
            self.error['status'] = status_code
        else:
            self.error['status'] = self.status_code

    def to_dict(self):
        return self.error

def get_payload():
    """ Performs sanity checks or decoding depending on the Content-Type,
    then returns the request payload as a dict. If request Content-Type is
    unsupported, restful_aborts with a 400 (Bad Request).

    .. versionchanged:: 0.0.9
       More informative error messages.
       request.get_json() replaces the now deprecated request.json


    .. versionchanged:: 0.0.7
       Native Flask request.json preferred over json.loads.

    .. versionadded: 0.0.5
    """
    content_type = request.headers['Content-Type'].split(';')[0]

    if content_type == 'application/json':
        try:
            return request.get_json()
        except BadRequest:
            return None
    elif content_type == 'application/x-www-form-urlencoded':
        return request.form if len(request.form) else \
                InvalidUsage('No form-urlencoded data supplied')
    else:
        InvalidUsage('Unknown or no Content-Type header supplied')


def str_to_date(string):
    """ Converts a RFC-1123 string to the corresponding datetime value.

    :param string: the RFC-1123 string to convert to datetime value.
    """
    return dateutil.parser.parse(string) if string else None

def date_to_str(date):
    """ Converts a datetime value to the corresponding RFC-1123 string.

    :param date: the datetime value to convert.
    """
    return datetime.datetime.strftime(date,'%a, %d %b %Y %H:%M:%S GMT') if date else None


def calc_hash(value):
    """ Computes and returns a valid ETag for the input value.

    :param value: the value to compute the ETag with.

    .. versionchanged:: 0.0.4
       Using bson.json_util.dumps over str(value) to make etag computation
       consistent between different runs and/or server instances (#16).
    """
    h = hashlib.sha1()
    h.update(dumps(value, sort_keys=True).encode('utf-8'))
    return h.hexdigest()


def document_etag(doc):
    return calc_hash({key:doc[key] for key in
                            doc if not key.startswith('_')})
