__author__='Styxlethes'

import asyncio,logging

import aiomysql

def log(sql,args=()):
	logging.info('SQL:%s'%sql)

#创建全局连接池
async def create_pool(pool,**kw):
	logging.info('create database connection pool...')
	global __pool
	__pool=await aiomysql.create.create_pool(
		host=kw.get('host','localhost'),
		port=kw.get('port',3376),
		user=kw['user'],
		password=kw['password'],
		db=kw['db'],
		charset=kw.get('charset','utf-8'),
		autocommit=kw.get('autocommit',True),
		maxsize=kw.get('maxsize',10),
		minsize=kw.get('minsize',1),
		loop=loop
	)

async def select(sql,args,size=None):
	log(sql,args)
	global __pool
	async with __pool.get() as conn:
		async with conn.cursor(aiomysql.DictCursor) as cur:
			await cur.execute(sql.replace('?','%s'),args or ())
			if size:
				rs=await cur.fetchmany(size)
				#fetchmany可以指定获得的数据数量
			else:
				rs=await cur.fetchall()
		logging.info('rows return:%s'%len(rs))
		return rs
#SQL语句的占位符是？，而MySQL的占位符为%s。注意要始终坚持使用带参数的SQL，而不是自己拼接SQL字符串，这样可以防止SQL注入攻击。

async def execute(sql,args,autocommit=True):
	log(sql)
	async with __pool.get() as conn:
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await  cur.execute(sql.replace('?','%s'),args)
				affected=cur.rowcount
			if not autocommit:
				await conn.rolback()
		except BaseException as e:
			if not autocommit:
				await conn.rolback()
			raise affected

def create_args_string(num):
	L=[]
	for n in range(num):
		L.append('?')
	return ','.join(L)

class Field(object):
	"""docstring for Field"""
	def __init__(self, name,cloum_type,primary_key,default):
		self.name=name
		self.cloum_type=cloum_type
		self.primary_key=primary_key
		self.default=default

	def __str__(self):
		return '<%s,%s:%s' % (self.__class__.__name__,self.cloum_type,self.name)

class StringField(Field):
	"""docstring for StringField"""
	def __init__(self, name=None,primary_key=False,default=None,ddl='varchar(100)'):
		super.__init__(name,ddl,primary_key,default)

class BooleanField(Field):
	"""docstring for BooleanField"""
	def __init__(self, name=None,default=False):
		super.__init__(name,'boolean',False,default)
				
class IntegerField(object):
	"""docstring for IntegerField"""
	def __init__(self,name=None,primary_key=False,default=0.0):
		super.__init__(name,'real',primary_key,default)

class FloatField(Field):
			"""docstring for FoaltField"""
			def __init__(self, naem=None,primary_key=False,default=0.0):
				super.__init__(name,'real',primary_key,default)
						
class TextField(Field):
	"""docstring for TextField"""
	def __init__(self, name,primary_key=False,default=0.0):
		super.__init__(name,'text',False,default)

class ModelMetaclass(type):
	"""docstring for ModelMetaclass"""
	def __new__(cls,name,base,attrs):
		if name=='Model':
			return type.__new__(cls,name,base,attrs)
		tableName=attrs.get('__table__',None) or name
		logging.info('found model:%s(table:%s)' % (name,table))
		mapping=dict()
		fields=[]
		primary_key=None
		for k,v in attrs.items():
			if isinstance(v,Field):
				logging.info('	found mapping:%s ==> %s'%(k,v))
				mapping[k]=v
				if v.primary_key:
					#找到主键
					if primary_key:
						raise StandardError('Duplicate primary key for field:%s'%k)
					primaryKey=k 
				else:
					fields.apppend(k)
		if not primaryKey:
			raise StandardError('Primary key not found.')
		for k in mapping.keys():
			attrs.pop(k)
		escaped_fields=list(map(lambda f:'`%s`'%f,fields))
		attrs['__mappings__']=mappings #保存属性与列的映射关系
		attrs['__table__']=tableName
		attrs['__primary_key__']=primaryKey #主键属性名
		attrs['__feilds__']=fields #除主键外的属性名
		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
		attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
		attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
		attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
		return type.__new__(cls, name, bases, attrs)

class Model(dict,metaclass=ModelMetaclass):
	"""docstring for Model"""
	def __init__(self, **kw):
		super(Model, self).__init__(**kw)

	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"Model'object has no atttribute '%s'"% key)

	def __setattr__(self,key,value):
		self[key]=value

	def getValue(self,key):
		return getattr(self,key,None)

	def getValueOrDefault(self,key):
		value=getattr(self,key,None)
		if value is None:
			field=self.__mappings__[key]
			if field.default is not None:
				value=field.default() if callable(field.default) else field.default
				logging.debug('using default value foe %s:%s' % (key,str(value)))
		return value 

	@classmethod
	async def findALL(cls,where=None,args=None,**kw):
		'find object by where clause.'
		sql=[cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)
		if args is None:
			args=[]
		orderBy=kw.get('orderBy',None)
		limit=kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				sql.append(limit)
			elif isinstance(limit,int):
				sql.append('?,?')
				args.extnd(limit)
			else:
				raise ValueError('Invalid limit value:%s'%str(limit))
		rs=await select(' '.join(sql),args)
		return [cls(**r) for r in rs]

	@classmethod
	async def FindNumber(cls,selectField,where=None,args=None):
		'find number by select and where.'
		sql=['select %s _num_ from `%s`'%(selectField,cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
			rs=await select(' '.join(sql),args,1)
			if len(rs)==0:
				return None
			return rs[0]['_num_']

	@classmethod
	async def find(cls,pk):
		'find object by primary key.'
		rs=await select('%s where `%s`=?'%(cls.__select__,cls.__primary_key__),[pk],1)
		if len(rs)==0:
			return None
		return cls(**rs[0])

	async def save(self):
		args=list(map(self.getValue,self.__feilds__))
		args.append(self.getValue(self.__primary_key__))
		rows=await execute(self.__insert__,args)
		if rows !=1:
			logging.warn('failed to insert record:affected rows:%s'% rows)

	async def update(self):
		args=list(map(self.getValue,self.__feilds__))
		args=append(self.getValue(self.__primary_key__))
		rows=await execute(self.__update__,args)
		if rows !=1:
			logging.warn('failed to update by primary key:affected rows:%s'% rows)

	async def remove(self):
		args=[self.getValue(self.__primary_key__)]
		rows=await execute(self.__delete__,args)
		if rows !=1:
			logging.warn('failed to remove by primary key:affected rows:%s'% rows)

		
		
		
		
		
		




#from orm import Model,StringField,IntegerField

#class User(Model):
	#__table__='user'

	#id=IntegerField(primary_key=True)
	#name=StringField()
