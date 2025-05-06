from peewee import *
from dotenv import load_dotenv
import os

load_dotenv()

db = MySQLDatabase(
    'quotr_bot',
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=os.getenv("MYSQL_HOST"),
    port=3306,
)

class Guild(Model):
    guildid = IntegerField(primary_key=True)
    quoteChannel = IntegerField(null=True)
    quoteRegex = TextField(null=True)
    quotesProcessedUntil = DateTimeField(default=0)
    
    class Meta:
        database = db
        table_name = 'guilds'
        
class Quote(Model):
    messageid = IntegerField(primary_key=True)
    guildid = ForeignKeyField(Guild, backref='quotes')
    author = IntegerField()
    content = TextField()
    
    class Meta:
        database = db
        table_name = 'quotes'

    
db.connect()
db.create_tables([Guild, Quote], safe=True)