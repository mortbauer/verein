from flask import Blueprint, current_app, render_template, request, make_response, jsonify
from flask.views import MethodView
from ..validation import Validator
from ..utils import get_payload, send_response, str_to_date

mod = Blueprint('accounting', __name__, url_prefix='/api/accounting')

buchungs_validator_put = Validator({
    'date':{'type':'datetime','required':True},
    'client':{'type':'string','required':True,'empty':False},
    'tags':{'type':'list'},
    'account':{'type':'string','required':True,'empty':False},
    'info':{'type':'string'},
    'splits':{'type':'list','required':True,'schema':{'type':'dict','schema':{
        'amount':{'type':'float','required':True,'forbidden':[0.0]},
        'category':{'type':'string','required':True},
        'comment':{'type':'string'},
    }}},
    'comment':{'type':'string'},
})
buchungs_validator = Validator({
    'date':{'type':'datetime','required':True},
    'client':{'type':'string','required':True,'empty':False},
    'tags':{'type':'list'},
    'account':{'type':'string','required':True,'empty':False},
    'info':{'type':'string'},
    'splits':{'type':'list','required':True,'schema':{'type':'dict','schema':{
        'amount':{'type':'float','required':True,'forbidden':[0.0]},
        'category':{'type':'string','required':True},
        'comment':{'type':'string'},
    }}},
    'comment':{'type':'string'},
})


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
        payload = get_payload()
        if payload:
            if 'date' in payload:
                payload['date'] = str_to_date(payload['date'])
            if not buchungs_validator_put.validate(payload):
                return send_response({
                    'status_code':400,
                    'message':'document didn\'t pass validation',
                    'issues':buchungs_validator_put.errors},status=400)
            splits = payload.pop('splits')
            for split in splits:
                data = payload.copy()
                data.update(split)
                current_app.db.buchungen.insert(data)
            return send_response({'status_code':200})
        else:
            return send_response({
                'status_code':400,
                'message':'no payload data provided'},status=400)

    def post(self):
        payload = get_payload()
        if payload:
            if 'date' in payload:
                payload['date'] = str_to_date(payload['date'])
            if not buchungs_validator.validate(payload):
                return send_response({
                    'status_code':400,
                    'message':'document didn\'t pass validation',
                    'issues':buchungs_validator.errors},status=400)
            current_app.db.buchungen.insert(payload)
            return send_response(payload)
        else:
            return send_response({
                'status_code':400,
                'message':'no payload data provided'},status=400)

class Search(MethodView):
    def post(self):
        payload = get_payload()
        if payload:
            search = create_search(payload)
            if not search:
                return send_response({
                    'status_code':400,
                    'message':'search must be dict'},status=400)
            docs = current_app.db.buchungen.find(search)
            return send_response({'_items':[doc for doc in docs]})
        else:
            return send_response({
                'status_code':400,
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
