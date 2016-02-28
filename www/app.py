#-*-coding:utf-8-*-

'a app module'

__author__='hecheng'

import logging; logging.basicConfig(level=logging.INFO)

import asyncio,os,json,time
from datetime import datetime

#aiohttp's document:aiohttp:readthedocs.org/en/stable
#aiohttp是基于asyncio实现的HTTP框架
from aiohttp import web

def index(request):
    return web.Response(body='<h1>Let\'s rock!</h1>'.encode('utf-8'))

#aiohtto的初始化函数init()是一个协程coroutine
@asyncio.coroutine
def init(loop):
    # http://aiohttp.readthedocs.org/en/stable/web_reference.html#application-and-router
    app=web.Application(loop=loop)
    app.router.add_route('GET','/',index)
    srv=yield from loop.create_server(app.make_handler(),'127.0.0.1',9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop=asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
