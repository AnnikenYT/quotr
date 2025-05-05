from peewee import *
from playhouse.migrate import SqliteMigrator, migrate

db = SqliteDatabase('data/database.db')

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

# Migrate the quotesProcesedUntil field to a DateTimeField
migrator = SqliteMigrator(db)
migrate(
    migrator.drop_column('guilds', 'quotesProcessedUntil'),
    migrator.add_column('guilds', 'quotesProcessedUntil', DateTimeField(default=0))
)