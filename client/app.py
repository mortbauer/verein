#!/usr/bin/env python
#coding=utf-8

import os
import sys
import requests
from requests import HTTPError
import simplejson as json
import argparse
from urlparse import urljoin

class Client(object):
    def __init__(self,base_url='http://localhost:5000/api/accounting/'):
        self._email = 'mortbauer@gmail.com'
        self._username = 'martin'
        self._password = 'martin'
        self.author = 'Martin Ortbauer'
        self.base_url = base_url
        self._headers = {'Accept': 'application/json',
                        'Content-Type': 'application/json; charset=UTF-8'}
        self._auth = (self._username,self._password)
        self._args = {'headers':self._headers,'auth':(self._username,self._password)}
        self._curies = {}


    def handle_errors(self,resp):
        if resp.status_code != 200:
            try:
                return resp.status_code,resp.json()
            except:
                return resp.status_code,{'message':resp.reason}
        else:
            return 200,resp.json()

    def get(self,url):
        try:
            r = requests.get(urljoin(self.base_url,url),**self._args)
            return self.handle_errors(r)
        except requests.RequestException:
            return 500, {'message':'server not reachable'}

    def post(self,url,doc):
        try:
            r = requests.post(urljoin(self.base_url,url),data=json.dumps(doc),**self._args)
            return self.handle_errors(r)
        except requests.RequestException:
            return 500, {'message':'server not reachable'}

    def options(self,url):
        try:
            r = requests.options(urljoin(self.base_url,url),**self._args)
            return self.handle_errors(r)
        except requests.RequestException:
            return 500, {'message':'server not reachable'}

    def delete(self,url):
        try:
            r = requests.delete(urljoin(self.base_url,url),**self._args)
            return self.handle_errors(r)
        except requests.RequestException:
            return 500, {'message':'server not reachable'}

    def patch(self,url,doc):
        try:
            r = requests.patch(urljoin(self.base_url,url),data=json.dumps(doc),**self._args)
            return self.handle_errors(r)
        except requests.RequestException:
            return 500, {'message':'server not reachable'}

    def put(self,url,doc):
        try:
            r = requests.put(urljoin(self.base_url,url),data=json.dumps(doc),**self._args)
            return self.handle_errors(r)
        except requests.RequestException:
            return 500, {'message':'server not reachable'}

    def _search_date(self,date=None,start=None,end=None):
        if date:
            search = date
        else:
            search  = {}
            if start:
                search['$gte'] = start
            if end:
                search['$lt'] = end
        return {'date':search}

    def _search_amount(self,amount=None,start=None,end=None):
        if amount:
            search = amount
        else:
            search  = {}
            if start:
                search['$gte'] = start
            if end:
                search['$lt'] = end
        return {'splits.amount':search}

def main(args=None):
    if not args:
        args = sys.argv[1:]

    client = Client()
    #client.login()

    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(title='subcommands',dest='subcommand')
    postparser = subparser.add_parser('post')
    postparser.add_argument('--markup',help='the markup of the blog post')
    postparser.add_argument('file',help='the source file')
    interactiveparser = subparser.add_parser('interact')
    options = parser.parse_args(args)

    if options.subcommand == 'post':
        # guess markup from extension
        resp = client.post(options.file,markup=options.markup)
        print(resp)
    elif options.subcommand == 'interact':
        #from .shell import Shell
        #s= Shell()
        #s.run({'cl':client})
        client._interactive()


if __name__ == '__main__':
    main()

