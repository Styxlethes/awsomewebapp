import logging; logging.basicConfig(level=logging.INFO)

import asyncio,os,json,time
from aiohttp import web
from datetime import datetime

def index(request):
	return web.Response(body=b'<h1>Awsome</h1>',content_type='text/html')


async def init(loop):
		app=web.Application(loop=loop)
		#添加常规的上网方式
		app.router.add_route('GET','/',index)
		#添加协程
		srv=await loop.create_server(app.make_handler(),'127.0.0.1',9000)
		#设置网络登录信息
		logging.info('server started at http://127.0.0.1:9000...')
		return srv

loop=asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()