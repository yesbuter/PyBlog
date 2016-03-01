# -*- coding:utf-8 -*-

'a simple orm module'

__author__='hecheng'

import asyncio,logging

#框架使用了aiohttp，一旦使用异步，系统每一层都得是异步
#所有用户都是由一个线程服务，协程的执行速度要快
#因此耗时的io操作不能在协程中以同步的方式调用
#aiomysql为mysql提供了异步io的驱动
import aiomysql

#打印执行的sql语句
def log(sql,args=()):
    logging.info('SQL:%s' % sql)

#-----------------------------------创建连接池----------------------------------
@asyncio.coroutine
def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    global __pool                    #连接池由全局变量存储
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host','localhost'),        #默认定义host为localhost
        port=kw.get('port',3306),               #默认定义mysql的端口为3306
        user=kw['user'],                        #user,password等都通过关键字参数传入
        password=kw['password'],                
        db=kw['db'],                            
        charset=kw.get('charset','utf8'),       #默认数据库字符集为ytf8
        autocommit=kw.get('autocommit',True),   #默认自动提交事务
        maxsize=kw.get('maxsize',10),           #连接池最大连接数为10
        minsize=kw.get('minsize',1),            #最少要求1个请求
        loop=loop                               #传递消息循环对象用于异步执行
    )

#----------------------------------封装SQL处理函数--------------------------------

#执行select语句
@asyncio.coroutine
def select(sql,args,size=None):             #参数：？
    
    log(sql,args)                        #打印传入的sql语句
    global __pool                        #为了区分复制给同名的局部变量
   
    #理解python中的with语句：
    #http://blog.csdn.net/suwei19870312/article/details/23258495
    #这里with语句封装了关闭conn和处理异常的工作
    with (yield from __pool) as conn:
        #？
        #执行select语句，返回结果集存在cur中
        cur = yield from conn.cursor(aiomysql.DictCursor)  
        yield from cur.execute(sql.replace('?','%s'),args or ())
       
        if size:                        #如果传入size参数，就通过fetchmany()获取最多制定数量的记录
            rs=yield from cur.fetchmany(size)
        else:                           #否则获取所有记录
            rs=yield from fur.fetchall()
        
        yield from cur.close()
        logging.info('rows returned:%s' % len(rs))  #记录条数
        
        return rs

#执行Inser,Update,Delete的通用函数
@asyncio.coroutine
def execute(sql,args):
    log(sql)
    with (yield from __pool) as conn:
        try:
            cur=yield from conn.cursor()
            yield from cur.execute(sql.replace('?','%s'),args)
            affected=cur.rowcount       #通过rowcount返回语句作用的结果数
        except BaseException as e:
            raise

        return affected



#---------------------------------------------定义orm的基类Model--------------------------
#---------------------------------------------和Mode的元类--------------------------------

#上层调用者视角：
#from orm import Model,StringField,IntegerField
#class User(Model):
#   __table__='user'
#   id=IntegerField(primary_key=True)
#   name=StringField()


#数据库表的一列/一个字段的对应类
class Field(object):
    
    def __init__(self,name,column_type,primary_key,default):
        self.name = name                        #属性名
        self.column_type = column_type          #属性类型
        self.primary_key = primary_key          #属性是否是主键
        self.default=default                    #属性的默认值

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__,self.column_type,self.name)             #规定类实例的打印结果


#Field的子类

class IntegerField(Field):              #INT类型，bigint,默认default为0
    
    def __init__(self,name=None,primary_key=False,default=0):
        super().__init__(name,'bigint',primary_key,default)

class StringFeild(Field):               #String类型，可传入ddl参数，默认default为None
    
    def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
        super().__init__(name,ddl,primary_key,default)

class BooleanFeild(Field):  #Bool类型，boolean,不能作为主键，默认dfault为False
    
    def __init__(self,name=None,default=False):
        super().__init__(name,'boolean',False,default)

class FloatField(Field):                #浮点类型,real，默认default为0.0
    
    def __init__(self,name=None,primary_key=False,default=0.0):
        super().__init__(name,'real',primary_key,default)

class TextFeild(Field):                 #文本类型,test，不能作为主键,默认default为none

    def __init__(self,name=None,default=None):
        super().__init__(name,'text',False,default)


#元类
class ModelMetaclass(type):
    
    def __new__(cls,name,bases,attrs):      #参数分别为：传入的类，实例的类名，类的父类的集合，类的属性/方法的集合
        
        if name=='Model':                   #排除基类本身
            return type.__new__(cls,name,bases,attrs)
        tableName=attrs.get('__table__',None) or name   #通过传入的类属性或类名获得数据库表名
        logging.info('found model:%s (table: %s)'% (name,tableName))
        
        #获取所有的Field和主键名
        mappings=dict()             #保存映射关系的字典
        fields=[]                   #保存Model类除主键外的字段名
        primaryKey=None             #保存Model类的主键字段名
        for k,v in attrs.items():   
            if isinstance(v,Field): #传入的类的属性是Field类型就加入mappings
                logging.info('found mapping:%s==>%s' % (k,v))
                mappings[k]=v       #k:属性名；v：实例
                if v.primary_key:   #如果v（Field类实例）的primary_key=True
                    
                    if primaryKey:  #如果primaryKey已经有了，就抛出错误
                        raise RuntimeError('Duplicate primary key for field:%s' % k)
                    primaryKey=k
                else:               #v不是主键时
                    fields.appends(k)   #非主键字段名存到fields里面
                
        if not primaryKey:          #如果遍历完还没有主键，抛出错误
            raise RuntimeError('Primary key not found')

        for k in mappings.keys():   #因为类属性与实例属性同名，要在映射建立之后即类属性已经没有用处之后删除类属性
            attrs.pop(k)

        #'attr'-->'`attr`'
        #不加`符号在mysql中可能报错，未验证
        escaped_fields = list(map(lambda f:'`s%`' % f,fields))

        attrs['__mappings__']=mappings      #保存属性和字段之间的映射关系
        attrs['__table__']=tableName
        attrs['__primary_key__']=primaryKey
        attrs['__fields__']=fields
        attrs['__select__']='select `%s`,%s from `%s`' % (primaryKey,','.join(escaped_fields),tableName)
        attrs['__insert__']='insert into `%s` (%s,`%s`) values(%s)' % (tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))         #问号太多，使用create_args_string函数来生成num个占位符的string
        attrs['__update__']='update `%s` set %s where `%s`=?' % (tableName,','.join(map(lambda f:'`%s`=?' % (mappings.get(f).name or f),fields)),primaryKey)
        attrs['__delete__']='delete from `%s` where `%s`=?' % (tableName,primaryKey)

#用在元类里面的函数
def create_args_string(num):
    #insert插入属性时，增加num个数量的占位符
    L=[]
    for n in range(num):
        L.append('?')
    return ','.join(L)

#------------------------------------------基类Model--------------------------------------
class Model(dict,metaclass=ModelMetaclass):
    #继承dict
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)
    
    #实现__getattr__和__setattr__即可普通的用instance.key的形式
    def __getattr__(self,key):     
        try:
            return self[key]        
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self,key,value):
        self[key]=value

    def getValue(self,key):
        return getattr(self,key,None)

    def getValueOrDefault(self,key):
        #当value为None时返回Field类设置的默认值
        value=getattr(self,key,None)        #key不存在就获取None
        if value is None:
            #self.__mappings__保存映射关系
            field=self.__mappings__[key]
            if field.default is not None:   #如果字段存在默认值，则使用默认值
                value=field.defaul
                logging.debug('using default value for %s: %s' % (key,str(value)))
                setattr(self,key,value)     #赋予实例默认zhi
        return value

#---------------------------------------Model的类方法--------------------------------

    @classmethod    
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        sql = [cls.__select__]  # 获取默认的select语句
        if where:   # 如果有where语句，则修改sql变量
            sql.append('where')  # sql里面加上where关键字
            sql.append(where)   # 这里的where实际上是colName='xxx'这样的条件表达式
        
        if args is None:    
            args = []

        orderBy = kw.get('orderBy', None)    # 从kw中查看是否有orderBy属性
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)

        limit = kw.get('limit', None)    # mysql中可以使用limit关键字
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):   # 如果是int类型则增加占位符
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:   # limit可以取2个参数，表示一个范围
                sql.append('?,?')
                args.extend(limit)
            else:       # 其他情况自然是语法问题
                raise ValueError('Invalid limit value: %s' % str(limit))
            # 在原来默认SQL语句后面再添加语句，要加个空格

        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]   # 返回结果，结果是list对象，里面的元素是dict类型的

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        # 获取行数
        # 这里的 _num_ 什么意思？别名？ 我估计是mysql里面一个记录实时查询结果条数的变量
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        # pdb.set_trace()
        if where:
            sql.append('where')
            sql.append(where)   # 这里不加空格？
        rs = yield from select(' '.join(sql), args, 1)  # size = 1
        if len(rs) == 0:  # 结果集为0的情况
            return None
        return rs[0]['_num_']   # 有结果则rs这个list中第一个词典元素_num_这个key的value值

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        # 根据主键查找
        # pk是dict对象
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    # 这个是实例方法
    @asyncio.coroutine
    def save(self):
        # arg是保存所有Model实例属性和主键的list,使用getValueOrDefault方法的好处是保存默认值
        # 将自己的fields保存进去
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        # pdb.set_trace()
        rows = yield from execute(self.__insert__, args)  # 使用默认插入函数
        if rows != 1:
            # 插入失败就是rows!=1
            logging.warn(
                'failed to insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):
        # 这里使用getValue说明只能更新那些已经存在的值，因此不能使用getValueOrDefault方法
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        # pdb.set_trace()
        rows = yield from execute(self.__update__, args)    # args是属性的list
        if rows != 1:
            logging.warn(
                'failed to update by primary key: affected rows: %s' % rows)

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        # pdb.set_trace()
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn(
                'failed to remove by primary key: affected rows: %s' % rows)
