from copy import deepcopy
from bson import ObjectId
import datetime
from flask import Blueprint, current_app, render_template, request, make_response, jsonify, g
from flask.views import MethodView
from ..utils import get_payload, send_response, str_to_date, serialize, Validator, get_docs
from ..login import check_valid_auth

# for CRUD operations see http://stackoverflow.com/a/630475/1607448
# TODO check for special forbidden operators see: http://docs.mongodb.org/manual/reference/limits/
mod = Blueprint('accounting', __name__, url_prefix='/api/accounting')
# secure the whole blueprint
mod.before_request(check_valid_auth)

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

def serialize_for_search(payload):
    for key in ('date','_edit_time'):
        if key in payload:
            for x in payload[key]:
                payload[key][x] = str_to_date(payload[key][x])

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
        return send_response({'_items':[doc for doc in docs],'status':'OK'})

    def post(self):
        """ create new transactions or update existing ones; in bulk possible"""
        docs = get_docs()
        if not docs:
            return send_response({
                'issues':'no data provided'},status=400)
        updated = []
        status = 'OK'
        for doc in docs:
            payload = serialize(doc,buchungs_schema)
            if not buchungs_validator.validate(payload):
                updated.append({'_item':payload,'status':'ERROR','issues':buchungs_validator.errors})
                status = 'Partial-OK'
                continue
            payload['_edit_time'] = datetime.datetime.now()
            #payload['_edit_by'] = g.user['username']
            if not '_id' in payload:
                updated.append(current_app.db.buchungen.insert(payload))
            else:
                query = {'_id':payload.pop('_id')}
                res = current_app.db.buchungen.update(query,payload)
                updated.append({'_item':query,'status':'OK' if res['ok'] else res})
        return send_response({'_items':updated,'status':status})

class Search(MethodView):
    def post(self):
        payload = get_payload()
        if payload:
            serialize_for_search(payload)
        docs = current_app.db.buchungen.find(payload)
        return send_response({'_items':[doc for doc in docs],'status':'OK'})


@mod.route('/clients/')
def payees():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('client'),'status':'OK'})

@mod.route('/categories/')
def categories():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('category'),'status':'OK'})

@mod.route('/accounts/')
def accounts():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('account'),'status':'OK'})

@mod.route('/tags/')
def tags():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('tag'),'status':'OK'})

@mod.route('/stats/<key>/<timestep>/')
def stats_key_timestep(key,timestep):
    opkey ='${0}'.format(key)
    optimestep = '${0}'.format(timestep)
    project = {'amount':1,key:opkey,timestep:{optimestep:'$date'}}
    group = {'_id':{timestep:optimestep,key:opkey},'amount':{'$sum':'$amount'}}
    sort = {'_id.%s'%timestep:1}
    result = current_app.db.buchungen.aggregate(
        [{'$project':project},{'$group':group},{'$sort':sort}])
    return send_response({'_items':result['result'],'status':'OK'})

mod.add_url_rule('/',view_func=Buchungen.as_view('buchungen'))
mod.add_url_rule('/search/',view_func=Search.as_view('search'))
