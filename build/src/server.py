#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback
from functools import wraps

from builtins import bytes
import click
import msgpack
import flask
from flask import Flask, render_template, copy_current_request_context
from flask import request, Response
from flask_socketio import SocketIO, emit
import eventlet


class GetterNotDefined(AttributeError):
    pass


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'username' and password == 'password'

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# import the user created module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import chat

app = Flask(__name__)
app.debug = False
socketio = SocketIO(app, binary=True, path='' + 'socket.io')
# not sure if this is secure or how much it matters
app.secret_key = os.urandom(256)

def context(func):
    def foo():
        with app.app_context():
            func()
    return foo


class Scheduler(object):

    def __init__(self, seconds, func):
        self.seconds = seconds
        self.func = func
        self.thread = None

    def start(self):
        self.thread = eventlet.spawn(self.run)

    def run(self):
        ret = eventlet.spawn(context(self.func))
        eventlet.sleep(self.seconds)
        try:
            ret.wait()
        except:
            traceback.print_exc()
        self.thread = eventlet.spawn(self.run)

    def stop(self):
        if self.thread:
            self.thread.cancel()


@app.route('/')
def index():
    return render_template('index.html')




@app.route('/static/bundle.js')
def getbundle():
    basedir = os.path.dirname(os.path.realpath(__file__))
    bundle_path = basedir + '/static/bundle.js'
    if os.path.isfile(bundle_path + '.gz'):
        bundle = open(bundle_path + '.gz', 'rb').read()
        response = flask.make_response(bundle)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Vary'] = 'Accept-Encoding'
        response.headers['Content-Length'] = len(response.data)
        return response
    else:
        return open(bundle_path, 'r').read()


@socketio.on('INITIALIZE')
def _():
    foo = copy_current_request_context(chat.update_chat)
    eventlet.spawn(foo)




@socketio.on('1#enter')
def _(*args):
    def wrapuser():
        uniq_events = set()
        uniq_events.update([('1#enter', 'talk', 'get')])
        uniq_events.remove(('1#enter', 'talk', 'get'))
        event_data = {}
        for ev in uniq_events:
            comp = getattr(chat, ev[1])
            if ev[2] is None:
                ename = ev[0]
                raise GetterNotDefined('{ctype} has no getter associated with event "on_{ename}"'
                                       .format(ctype=type(comp), ename=ename[ename.find('#') + 1:]))
            getter = getattr(comp, ev[2])
            event_data[ev[0]] = getter()

        event_data['1#enter'] = chat.talk._get(
            msgpack.unpackb(bytes(args[0]['data']), encoding='utf8')
        )

        user_args = []
        user_args.append(event_data['1#enter'])
        chat.entered(*user_args)

    foo = copy_current_request_context(wrapuser)
    eventlet.spawn(foo)

@socketio.on('2#click')
def _(*args):
    def wrapuser():
        uniq_events = set()
        uniq_events.update([('2#click', 'click', None)])
        uniq_events.remove(('2#click', 'click', None))
        event_data = {}
        for ev in uniq_events:
            comp = getattr(chat, ev[1])
            if ev[2] is None:
                ename = ev[0]
                raise GetterNotDefined('{ctype} has no getter associated with event "on_{ename}"'
                                       .format(ctype=type(comp), ename=ename[ename.find('#') + 1:]))
            getter = getattr(comp, ev[2])
            event_data[ev[0]] = getter()


        user_args = []
        chat.clicked(*user_args)

    foo = copy_current_request_context(wrapuser)
    eventlet.spawn(foo)


@click.command()
@click.option('--host', '-h', default='0.0.0.0', help='Host IP')
@click.option('--port', '-p', default=9991, help='port number')
def main(host, port):
    scheds = []
    sched = Scheduler(5,
                      chat.update_chat)
    scheds.append(sched)

    for sched in scheds:
        sched.start()
    socketio.run(app, host=host, port=port)
    for sched in scheds:
        sched.stop()

if __name__ == '__main__':
    main()