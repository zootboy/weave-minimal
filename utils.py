#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from werkzeug import Response

import os
import re
import base64
import struct
import sqlite3

from os.path import join, isfile
from hashlib import sha1

try:
    import json
except ImportError:
    import simplejson as json


class WeaveException(Exception):
    pass


def path(dir, user, passwd):
    """return joined path to database using data_dir + '/' + user.sha1(passwd)
    -- a bit truncated though. And salted.
    """
    salt = r'\x14Q\xd4JbDk\x1bN\x84J\xd0\x05\x8a\x1b\x8b\xa6&V\x1b\xc5\x91\x97\xc4'
    return join(dir, (user + '.' + sha1(salt+passwd).hexdigest()[:16]))


def encode(uid):
    if re.search('[^A-Z0-9._-]', uid, re.I):
        return base64.b32encode(sha1(uid).digest()).lower()
    return uid


def initialize(uid, passwd, data_dir):

    dbpath = path(data_dir, uid, passwd)

    if not os.path.isdir:
        os.mkdir(data_dir)

    try:
        os.unlink(dbpath)
    except OSError:
        pass

    with sqlite3.connect(dbpath) as con:
        con.commit()
    print '[info] database for `%s` created at `%s`' % (uid, dbpath)


class login:
    """login decorator using HTTP Basic Authentication. Pattern based on
    http://flask.pocoo.org/docs/patterns/viewdecorators/"""

    def __init__(self, methods=['GET', 'POST', 'DELETE', 'PUT']):
        self.methods = methods

    def __call__(self, f):

        def dec(env, req, *args, **kwargs):
            """This decorater function will send an authenticate header, if none
            is present and denies access, if HTTP Basic Auth fails."""
            if req.method not in self.methods:
                return f(env, req, *args, **kwargs)
            if not req.authorization:
                response = Response('Unauthorized', 401)
                response.www_authenticate.set_basic('Weave')
                return response
            else:
                user = req.authorization.username
                passwd = req.authorization.password
                if not isfile(path(env['data_dir'], user, passwd)):
                    # return Response('Forbidden', 403)
                    return Response('Unauthorized', 401)  # kinda stupid
                return f(env, req, *args, **kwargs)
        return dec


def wbo2dict(res):
    """converts sqlite table to WBO (dict [json-parsable])"""
    return {'id': res[0], 'modified': round(res[1], 2),
            'sortindex': res[2], 'payload': res[3], 'ttl': res[4]}


def convert(value, mime):
    """post processor producing lists in application/newlines format."""

    if mime and mime.endswith(('/newlines', '/whoisi')):
        try:
            value = value["items"]
        except (KeyError, TypeError):
            pass

        if mime.endswith('/whoisi'):
            res = []
            for record in value:
                js = json.dumps(record)
                res.append(struct.pack('!I', len(js)) + js)
            return ''.join(res), mime
        else:
            return '\n'.join(json.dumps(item) for item in value), mime
    else:
        return json.dumps(value), 'application/json'
