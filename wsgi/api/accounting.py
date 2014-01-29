from copy import deepcopy
from bson import ObjectId
import datetime
from flask import Blueprint, current_app, render_template, request, make_response, jsonify, g
from flask.views import MethodView
from ..utils import get_payload, send_response, str_to_date, serialize, Validator, get_docs
from ..login import check_valid_auth

# for CRUD operations see http://stackoverflow.com/a/630475/1607448

mod = Blueprint('accounting', __name__, url_prefix='/api/accounting')
# secure the whole blueprint
#mod.before_request(check_valid_auth)

buchungs_schema = {
    'date':{'type':'datetime','required':True},
    'client':{'type':'string','required':True,'empty':False},
    'tags':{'type':'list'},
    'account':{'type':'string','required':True,'empty':False},
    'info':{'type':'string'},
    'amount':{'type':'float','required':True,'forbidden':[0.0]},
    'category':{'type':'string','required':False},
    'comment':{'type':'string'},
    '_edit_time':{'type':'datetime','required':False},
    '_edit_by':{'type':'string','required':False},
    '_id':{'type':'objectid','required':False},
}
buchungs_validator = Validator(buchungs_schema)

def convert_dates(payload):
    if 'date' in payload:
        if isinstance(payload['date'],str):
            payload['date'] = str_to_date(payload['date'])
        elif isinstance(payload['date'],dict):
            for key,value in payload['date'].items():
                payload['date'][key] = str_to_date(value)
    return payload

def create_search(payload):
    search = None
    if isinstance(payload,dict):
        search = convert_dates(payload)
    elif isinstance(payload,list):
        search = {}
        for pay in payload:
            search.update(convert_dates(pay))
    return search


class Buchungen(MethodView):
    def get(self):
        """ get all transactions"""
        docs = current_app.db.buchungen.find()
        return send_response({'_items':[doc for doc in docs]})

    def post(self):
        """ create new transactions or update existing ones; in bulk possible"""
        docs = get_docs()
        if not docs:
            return send_response({
                'message':'no data provided'},status=400)
        updated = []
        for doc in docs:
            payload = serialize(doc,buchungs_schema)
            if not buchungs_validator.validate(payload):
                return send_response({
                    'issues':buchungs_validator.errors},status=400)
            payload['_edit_time'] = datetime.datetime.now()
            #payload['_edit_by'] = g.user['username']
            if not '_id' in payload:
                updated.append(current_app.db.buchungen.insert(payload))
            else:
                query = {'_id':payload.pop('_id')}
                updated.append(current_app.db.buchungen.update(query,payload))
        return send_response({'_items':updated,'status':'Ok'})

class Search(MethodView):
    def post(self):
        payload = get_payload()
        if payload:
            search = serialize(payload,buchungs_schema)
        else:
            search = {}
        docs = current_app.db.buchungen.find(search)
        return send_response({'_items':[doc for doc in docs]})


@mod.route('/payees/')
def payees():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('payee')})

@mod.route('/categories/')
def categories():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('category')})

@mod.route('/accounts/')
def accounts():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('account')})

@mod.route('/tags/')
def tags():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('tag')})


mod.add_url_rule('/',view_func=Buchungen.as_view('buchungen'))
mod.add_url_rule('/search/',view_func=Search.as_view('search'))
