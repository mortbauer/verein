from copy import deepcopy
from bson import ObjectId
import datetime
from flask import Blueprint, current_app, render_template, request, make_response, jsonify, g
from flask.views import MethodView
from ..utils import get_payload, send_response, str_to_date, serialize, Validator, get_docs
from ..login import check_valid_auth

mod = Blueprint('accounting', __name__, url_prefix='/api/accounting')
# secure the whole blueprint
#mod.before_request(check_valid_auth)

buchungs_schema_put = {
    'date':{'type':'datetime','required':True},
    'client':{'type':'string','required':True,'empty':False},
    'tags':{'type':'list'},
    'account':{'type':'string','required':True,'empty':False},
    'info':{'type':'string'},
    'splits':{'type':'list','required':True,'empty':False,'schema':{'type':'dict','schema':{
        'amount':{'type':'float','required':True,'forbidden':[0.0]},
        'category':{'type':'string','required':True},
        'comment':{'type':'string'},
    }}},
    'comment':{'type':'string'},
}
buchungs_validator_put = Validator(buchungs_schema_put)

buchungs_schema = {
    'date':{'type':'datetime','required':True},
    'client':{'type':'string','required':True,'empty':False},
    'tags':{'type':'list'},
    'account':{'type':'string','required':True,'empty':False},
    'info':{'type':'string'},
    'amount':{'type':'float','required':True,'forbidden':[0.0]},
    'category':{'type':'string','required':True},
    'comment':{'type':'string'},
    '_edit_time':{'type':'datetime','required':True},
    '_edit_by':{'type':'string','required':True},
    '_id':{'type':'objectid','required':True},
}
buchungs_validator = Validator(buchungs_schema)
unwind =[
            {'$unwind':'$splits'},
            {'$project':{
                'date':1,
                'client':1,
                'tags':1,
                'account':1,
                'info':1,
                'amount':'$splits.amount',
                'category':'$splits.category',
                'comment':{'$concat':['$splits.comment',' ','$comment']},
                '_edit_by':1,
                '_edit_time':1}
            }
        ]

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
        docs = current_app.db.buchungen.find()
        return send_response({'_items':[doc for doc in docs]})

    def put(self):
        docs = get_docs()
        if not docs:
            return send_response({
                'message':'no data provided'},status=400)
        inserted = []
        for doc in docs:
            payload = serialize(doc,buchungs_schema_put)
            if not buchungs_validator_put.validate(payload):
                return send_response({
                    'issues':buchungs_validator_put.errors},status=400)
            payload['_edit_time'] = datetime.datetime.now()
            #payload['_edit_by'] = g.user['username']
            # unwind splits and insert them as multiple docs
            splits = payload.pop('splits')
            gcomment = payload.get('comment','')
            for split in splits:
                newdoc = deepcopy(payload)
                newdoc['amount'] = split['amount']
                newdoc['category'] = split.get('category')
                if split.get('comment','') and gcomment:
                    newdoc['comment'] = '; '.join((split.get('comment',''),gcomment))
                else:
                    newdoc['comment'] = max(split.get('comment',''),gcomment)
                newdoc['_id'] = ObjectId()
                current_app.db.buchungen.insert(newdoc)
                inserted.append(newdoc)
        return send_response({
            'message':'inserted %s transactions'%len(inserted),
            '_items':inserted})

    def patch(self):
        docs = get_docs()
        if not docs:
            return send_response({
                'message':'no data provided'},status=400)
        updated = []
        for doc in docs:
            payload = serialize(doc,buchungs_schema)
            payload['_edit_time'] = datetime.datetime.now()
            if not buchungs_validator.validate_update(payload):
                return send_response({
                    'issues':buchungs_validator.errors},status=400)
            if not '_id' in payload:
                return send_response({
                    'issues':{'_id':'required field'}},status=400)
            _id = payload.pop('_id')
            current_app.db.buchungen.update({'_id':_id},{'$set':payload})
            updated.append(current_app.db.buchungen.find_one(_id))
        return send_response({'message':'updated %s docs'%len(updated),'_items':updated})

class Search(MethodView):
    def post(self):
        payload = get_payload()
        if payload:
            search = create_search(payload)
            if not search:
                return send_response({
                    'message':'search must be dict'},status=400)
            docs = current_app.db.buchungen.find(search)
            return send_response({'_items':[doc for doc in docs]})
        else:
            return send_response({
                'message':'no payload data provided'},status=400)


@mod.route('/payees/')
def payees():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('payee')})

@mod.route('/categories/')
def categories():
    return send_response(
        {'_items':current_app.db.buchungen.distinct('splits.category')})

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
