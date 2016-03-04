import sys,logging
import orm,asyncio
from models import User,Blog,Comment

@asyncio.coroutine
def test(loop):
    logging.error('1111111')
    yield from orm.create_pool(loop=loop,user='pyblog_data',password='pyblog_data',db='pyblog')
    logging.error('2222222')
    u=User(name='Test',email='test@example.com',passwd='1234567890',image='blank')
    logging.error('333333')
    yield from u.save()

if __name__=='__main__':
    loop=asyncio.get_event_loop()
    logging.error('beging')
    loop.run_until_complete(asyncio.wait([test(loop)]))
    loop.close()
    if loop.is_closed():
        sys.exit(0)
