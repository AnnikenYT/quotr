import discord
from discord.ext import commands
import os # default module
from dotenv import load_dotenv
from db import *
import asyncio
from logger import logger
from extractQuote import extractQuote
from quotes import *
from quoteImage import add_text_to_gif

load_dotenv() # load all the variables from the env file
intends = discord.Intents.default() # create the intents object
intends.reactions = True # enable the reactions intent
intends.messages = True # enable the messages intent
bot = discord.Bot(intends=intends) # create the bot object

guild_ids = [int(guildid) for guildid in os.getenv('GUILD_IDS').split(',')] # get the guild ids from the env file

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} - {bot.user.id}')
    logger.info('------')
    # check if the database is connected
    connection_errors = 0
    while db.is_closed():
        if connection_errors > 5:
            logger.error('Could not connect to the database after 5 attempts. Exiting...')
            await bot.close()
        connection_errors += 1
        logger.info('Attempting to connect to the database...')
        try:
            db.connect()
            logger.info('Database connected')
        except Exception as e:
            logger.error(f'Error connecting to database: {e}')
            await asyncio.sleep(5)
    
# on guild join, create a new guild in the database
@bot.event
async def on_guild_join(guild):
    logger.info(f'Joined guild: {guild.name} - {guild.id}')
    try:
        Guild.create(guildid=guild.id)
        logger.info(f'Created new guild in database: {guild.name} - {guild.id}')
    except Exception as e:
        logger.error(f'Error creating new guild in database: {e}')
# on guild remove, delete the guild from the database
@bot.event
async def on_guild_remove(guild):
    logger.info(f'Left guild: {guild.name} - {guild.id}')
    try:
        Guild.delete().where(Guild.guildid == guild.id).execute()
        logger.info(f'Deleted guild from database: {guild.name} - {guild.id}')
    except Exception as e:
        logger.error(f'Error deleting guild from database: {e}')
        
# on message write, if the message is in the guild's quote channel, and the message is a quote, save the quote to the database
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    guild, _ = Guild.get_or_create(guildid=message.guild.id)
    if message.channel.id == guild.quoteChannel:
        quote = extractQuote(message.content)
        if quote:
            try:
                Quote.create(messageid=message.id, guildid=guild, author=quote[1], content=quote[0])
                logger.info(f'Created new quote in database: {message.id} - {message.guild.name} - {message.guild.id}')
            except Exception as e:
                logger.error(f'Error creating new quote in database: {e}')
        else:
            await message.reply('I couldn\'t find a quote in that message. The channel description might contain a formatting description!', delete_after=5)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.author == bot.user:
        return
    guild, _ = Guild.get_or_create(guildid=after.guild.id)
    if after.channel.id == guild.quoteChannel:
        quote = extractQuote(after.content)
        if quote:
            try:
                Quote.update({Quote.content: quote[0], Quote.author: quote[1]}).where(Quote.messageid == after.id).execute()
                logger.info(f'Updated quote in database: {after.id} - {after.guild.name} - {after.guild.id}')
            except Exception as e:
                logger.error(f'Error creating new quote in database: {e}')
                
# if a message is deleted, delete the quote from the database
@bot.event
async def on_message_delete(message: discord.Message):
    if message.author == bot.user:
        return
    guild, _ = Guild.get_or_create(guildid=message.guild.id)
    if message.channel.id == guild.quoteChannel:
        try:
            Quote.delete().where(Quote.messageid == message.id).execute()
            logger.info(f'Deleted quote from database: {message.id} - {message.guild.name} - {message.guild.id}')
        except Exception as e:
            logger.error(f'Error deleting quote from database: {e}')

@bot.slash_command(name='setquotechannel', description='Set the quote channel for the guild', guild_ids=guild_ids)
@commands.has_permissions(manage_guild=True)
async def set_quote_channel(ctx, channel: discord.TextChannel = None):
    if channel is None:
        # use the current channel if no channel is provided
        channel = ctx.channel
    if channel.type != discord.ChannelType.text:
        await ctx.respond('Please select a text channel.', ephemeral=True)
        return
    await ctx.defer(ephemeral=True)
    guild, _ = Guild.get_or_create(guildid=ctx.guild.id)
    guild.quoteChannel = channel.id
    guild.save()
    
    # send an embed message to the channel
    embed = discord.Embed(title='Quote Channel Set', description=f'The quote channel has been set to {channel.mention}. I\'ll scan the last `500` Messages for quotes. Any new messages will also be scanned.', color=0x00ff00)
    embed.add_field(name='Channel', value=channel.mention, inline=False)
    # start processing the channel messages, but don't wait for it to finish
    task = asyncio.create_task(processChannelMessages(channel))
    # Add buttons to clear the quotes
    view = discord.ui.View(timeout=60)
    button = discord.ui.Button(label='Clear Quotes', style=discord.ButtonStyle.danger)
    async def button_callback(interaction):
        if interaction.user != ctx.author:
            await interaction.response.send_message('You are not allowed to use this button.', ephemeral=True)
            return
        await interaction.response.send_message('Clearing quotes...', ephemeral=True)
        # for each quote in the database, check if the message has a reaction
        await clearQuotes(channel, ctx.guild.id, bot.user)
        await interaction.followup.send('Quotes cleared', ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    button = discord.ui.Button(label='Stop Processing', style=discord.ButtonStyle.primary)
    async def button_callback(interaction):
        if interaction.user != ctx.author:
            await interaction.response.send_message('You are not allowed to use this button.', ephemeral=True)
            return
        await interaction.response.send_message('Stopping processing...', ephemeral=True)
        task.cancel()
        await interaction.followup.send('Processing stopped', ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    await ctx.respond(embed=embed, view=view, ephemeral=True)
    logger.info(f'Set quote channel for guild: {ctx.guild.name} - {ctx.guild.id} - {channel.name} - {channel.id}')

# scan command
@bot.slash_command(name='scan', description='Scan all channels for quotes', guild_ids=guild_ids)
@commands.has_permissions(manage_guild=True)
async def scan(ctx):
    await ctx.defer(ephemeral=True)
    guild, _ = Guild.get_or_create(guildid=ctx.guild.id)
    if guild.quoteChannel == None:
        await ctx.respond('Please set a quote channel first.', ephemeral=True)
        return
    channel = bot.get_channel(guild.quoteChannel)
    if channel is None:
        await ctx.respond('Quote channel not found. Please set a quote channel first.', ephemeral=True)
        return
    # start processing the channel messages, but don't wait for it to finish
    task = asyncio.create_task(processChannelMessages(channel))
    # send an embed message to the channel
    embed = discord.Embed(title='Quote Channel Scanning', description=f'Scanning the quote channel {channel.mention} for quotes. This may take a while.', color=0x00ff00)
    embed.add_field(name='Channel', value=channel.mention, inline=False)
    await ctx.respond(embed=embed, ephemeral=True)

@bot.slash_command(name='setquoteregex', description='Advanced. Group 1 is the quote, group 2 is the author. Reverse the groups with reverse=True', guild_ids=guild_ids)
@commands.has_permissions(manage_guild=True)
async def set_quote_regex(ctx, regex: str, reverse: bool = False):
    guild, _ = Guild.get_or_create(Guild.guildid == ctx.guild.id)
    guild.quoteRegex = regex
    guild.save()
    await ctx.respond(f'Quote regex set to {regex}')

@bot.slash_command(name='clearquotes', description='Clear all quotes from the database', guild_ids=guild_ids)
@commands.has_permissions(manage_guild=True)
async def clear_quotes(ctx):
    # Ask for confirmation
    view = discord.ui.View(timeout=60)
    button = discord.ui.Button(label='Confirm', style=discord.ButtonStyle.danger)
    async def button_callback(interaction):
        if interaction.user != ctx.author:
            await interaction.response.send_message('You are not allowed to use this button.', ephemeral=True)
            return
        await interaction.response.send_message('Clearing quotes...', ephemeral=True)
        # for each quote in the database, check if the message has a reaction
        await clearQuotes(ctx.channel, ctx.guild.id, bot.user)
        await interaction.followup.send('Quotes cleared', ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    button = discord.ui.Button(label='Cancel', style=discord.ButtonStyle.primary)
    async def button_callback(interaction):
        if interaction.user != ctx.author:
            await interaction.response.send_message('You are not allowed to use this button.', ephemeral=True)
            return
        await interaction.response.send_message('Cancelled', ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    embed = discord.Embed(title='Clear Quotes', description='Are you sure you want to clear all quotes from the database?', color=0xff0000)
    await ctx.respond(embed=embed, view=view, ephemeral=True)
    
@bot.slash_command(name='quote', description='Get a random quote from the database', guild_ids=guild_ids)
async def get_quote(ctx):
    quotes = Quote.select().where(Quote.guildid == ctx.guild.id)
    if quotes.count() == 0:
        await ctx.respond('No quotes found in the database.', ephemeral=True)
        return
    quote = quotes.order_by(fn.Random()).get()
    embed = discord.Embed(title='Random Quote', description=quote.content, color=0x00ff00)
    embed.add_field(name='Author', value=quote.author, inline=False)
    # jump to the message
    # get guild from the database
    guild = Guild.get_or_none(guildid=ctx.guild.id)
    if guild:
        # get the channel from the database
        channel = bot.get_channel(guild.quoteChannel)
        if channel:
            try:
                message = await channel.fetch_message(quote.messageid)
                if message:
                    embed.add_field(name='Message Link', value=f'[Jump to Message]({message.jump_url})', inline=False)
            except discord.NotFound:
                embed.add_field(name='Message Link', value='Message not found', inline=False)
    await ctx.respond(embed=embed)
    
@bot.slash_command(name='guess', description='Start a guessing game', guild_ids=guild_ids)
async def guess(ctx: discord.ApplicationContext):
    await ctx.defer()
    quotes = Quote.select().where(Quote.guildid == ctx.guild.id)
    if quotes.count() == 0:
        await ctx.respond('No quotes found in the database.', ephemeral=True)
        return
    quote = quotes.order_by(fn.Random()).get()
    embed = discord.Embed(title='Guess the Quote', description=quote.content, color=0x00ff00)
    embed.add_field(name='Author', value='?', inline=False)
    view = discord.ui.View(timeout=120)
    button = discord.ui.Button(label='Reveal', style=discord.ButtonStyle.primary)
    origin_interaction = None
    async def button_callback(interaction):
        embed.set_field_at(0, name='Author', value=quote.author, inline=False)
        guild = Guild.get_or_none(guildid=ctx.guild.id)
        if guild:
            channel = bot.get_channel(guild.quoteChannel)
            if channel:
                try:
                    message = await channel.fetch_message(quote.messageid)
                    if message:
                        embed.add_field(name='Message Link', value=f'[Jump to Message]({message.jump_url})', inline=False)
                except discord.NotFound:
                    logger.error(f'Message not found: {quote.messageid} - {channel.name} - {channel.id}')
        await interaction.response.edit_message(embed=embed, view=view)
    button.callback = button_callback
    view.add_item(button)
    # add button to delete the quote
    button = discord.ui.Button(label='Not a quote!', style=discord.ButtonStyle.danger)
    async def button_callback(interaction: discord.Interaction):
        await interaction.response.send_message('Deleting quote...', ephemeral=True)
        Quote.delete().where(Quote.messageid == quote.messageid).execute()
        await interaction.followup.send('Quote deleted', ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    await add_text_to_gif('assets/background.gif', f'temp/{ctx.channel_id}.gif', quote.content)
    file = discord.File(f'temp/{ctx.channel_id}.gif', filename=f'{ctx.channel_id}.gif')
    embed.set_image(url=f'attachment://{ctx.channel_id}.gif')
    await ctx.respond(embed=embed, file=file, view=view)
    os.remove(f'temp/{ctx.channel_id}.gif')  # remove the gif after sending
    

@bot.slash_command(name='guildinfo', description='Get information about the guild', guild_ids=guild_ids)
async def guild_info(ctx):
    guild, _ = Guild.get_or_create(guildid=ctx.guild.id)
    embed = discord.Embed(title='Guild Info', description=f'Information about the guild {ctx.guild.name}', color=0x00ff00)
    embed.add_field(name='Guild ID', value=guild.guildid, inline=False)
    embed.add_field(name='Quote Channel', value=guild.quoteChannel, inline=False)
    embed.add_field(name='Quote Regex', value=guild.quoteRegex, inline=False)
    embed.add_field(name='Quotes Processed Until', value=guild.quotesProcessedUntil, inline=False)
    embed.add_field(name='Quotes Processed', value=Quote.select().where(Quote.guildid == guild).count(), inline=False)
    await ctx.respond(embed=embed)

bot.run(os.getenv('DISCORD_TOKEN')) # run the bot with the token