#coding=utf-8
import cerberus
from abc import ABCMeta, abstractmethod
import datetime
from bson import ObjectId
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

import cerberus


class Validator(cerberus.Validator):
    """ A cerberus.Validator subclass adding the `unique` contraint to
    Cerberus standard validation.

    :param schema: the validation schema, to be composed according to Cerberus
                   documentation.
    :param resource: the resource name.

    .. versionchanged:: 0.0.6
       Support for 'allow_unknown' which allows to successfully validate
       unknown key/value pairs.

    .. versionchanged:: 0.0.4
       Support for 'transparent_schema_rules' introduced with Cerberus 0.0.3,
       which allows for insertion of 'default' values in POST requests.
    """
    def __init__(self, schema,**kwargs):
        super(Validator, self).__init__(schema, transparent_schema_rules=True,**kwargs)

    def _validate_forbidden(self, forbidden, field, value):
        if value in forbidden:
            self._error(field,"value '%s' is forbidden"%value)

    def _validate_empty(self,empty,field,value):
        super(self.__class__,self)._validate_empty(empty,field,value)
        if isinstance(value,list) and len(value) == 0 and not empty:
            self._error(field, cerberus.errors.ERROR_EMPTY_NOT_ALLOWED)

    def _validate_type_objectid(self, field, value):
        """ Enables validation for `objectid` schema attribute.

        :param field: field name.
        :param value: field value.
        """
        if not re.match('[a-f0-9]{24}', value):
            self._error(field, ERROR_BAD_TYPE % 'ObjectId')

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

def serialize(document, schema):
    """ Recursively handles field values that require data-aware serialization.
    Relies on the app.data.serializers dictionary.

    .. versionadded:: 0.1.1
    """
    serializers ={
        'datetime':str_to_date,
        'objectid': ObjectId,
    }
    for field in document:
        if field in schema:
            field_schema = schema[field]
            field_type = field_schema['type']
            if 'schema' in field_schema:
                field_schema = field_schema['schema']
                if 'dict' in (field_type, field_schema.get('type', '')):
                    # either a dict or a list of dicts
                    embedded = [document[field]] if field_type == 'dict' \
                        else document[field]
                    for subdocument in embedded:
                        if 'schema' in field_schema:
                            serialize(subdocument,
                                        schema=field_schema['schema'])
                else:
                    # a list of one type, arbirtrary length
                    field_type = field_schema['type']
                    if field_type in serializers:
                        i = 0
                        for v in document[field]:
                            document[field][i] = \
                                serializers[field_type](v)
                            i += 1
            elif 'items' in field_schema:
                # a list of multiple types, fixed length
                i = 0
                for s, v in zip(field_schema['items'], document[field]):
                    field_type = s['type'] if 'type' in s else None
                    if field_type in serializers:
                        document[field][i] = \
                            serializers[field_type](
                                document[field][i])
                    i += 1
            elif field_type in serializers:
                # a simple field
                document[field] = \
                    serializers[field_type](document[field])
    return document

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
    return datetime.datetime.strftime(date,'%d.%m.%Y') if date else None


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
