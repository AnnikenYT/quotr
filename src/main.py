import discord
from discord.ext import commands
import os # default module
from dotenv import load_dotenv
from util.db import *
import asyncio
from util.logger import logger
from util.quotes import process_message, processChannelMessages, clearQuotes
from util.images import create_quote_image
import random

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
    if message.channel.id != guild.quoteChannel:
        return
    await process_message(message)

@bot.event
async def on_raw_message_edit(event: discord.RawMessageUpdateEvent):
    guild, _ = Guild.get_or_create(guildid=event.guild_id)
    if event.channel_id != guild.quoteChannel:
        return
    message_id = event.message_id
    # get the message object
    after = await bot.get_channel(event.channel_id).fetch_message(message_id)
    if after is None:
        return
    if after.author == bot.user:
        return
    await process_message(after)
        
                
# if a message is deleted, delete the quote from the database
@bot.event
async def on_message_delete(message: discord.Message):
    if message.author == bot.user:
        return
    guild, _ = Guild.get_or_create(guildid=message.guild.id)
    if message.channel.id != guild.quoteChannel:
        return
    # delete the quote from the database
    quote = Quote.get_or_none(Quote.messageid == message.id)
    if quote:
        quote.delete_instance()
        logger.info(f'Deleted quote from database: {quote.quote} - {quote.author} - {message.id}')
    else:
        logger.info(f'Quote not found in database: {message.id}')

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
    
    # Add buttons
    view = discord.ui.View(timeout=60)

    # Add Stop Button
    button = discord.ui.Button(label='Stop Processing', style=discord.ButtonStyle.danger)
    async def button_callback(interaction):
        await interaction.response.send_message('Stopping processing...', ephemeral=True)
        task.cancel()
        await interaction.followup.send('Processing stopped', ephemeral=True)
    button.callback = button_callback
    view.add_item(button)
    
    await ctx.respond(embed=embed, view=view, ephemeral=True)
    
    logger.info(f'Set quote channel for guild: {ctx.guild.name} - {ctx.guild.id} - {channel.name} - {channel.id}')

# scan command
@bot.slash_command(name='scan', description='Scan quote channel for quotes', guild_ids=guild_ids)
@commands.has_permissions(manage_guild=True)
async def scan(ctx, limit: int = 500):
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
    task = asyncio.create_task(processChannelMessages(channel, limit))
    
    # create a view
    view = discord.ui.View(timeout=120)
    
    # add a button to stop the scan
    button = discord.ui.Button(label='Stop Scan', style=discord.ButtonStyle.danger)
    async def button_callback(interaction):
        await interaction.response.send_message('Stopping scan...', ephemeral=True)
        task.cancel()
        await interaction.followup.send('Scan stopped', ephemeral=True)
    
    button.callback = button_callback
    view.add_item(button)
    
    # send an embed message to the channel
    embed = discord.Embed(title='Quote Channel Scanning', description=f'Scanning the quote channel {channel.mention} for quotes. This may take a while.', color=0x00ff00)
    embed.add_field(name='Channel', value=channel.mention, inline=False)
    await ctx.respond(embed=embed, ephemeral=True, view=view)

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
    quote = quotes.order_by(fn.RAND()).get()
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
    # Get a random quote from the database
    quotes = Quote.select().where(Quote.guildid == ctx.guild.id)
    if quotes.count() == 0:
        await ctx.respond('No quotes found in the database.', ephemeral=True)
        return
    quote = quotes.order_by(fn.RAND()).get()
    
    # Create Images
    background_color = random.choice(["#7289da", "#ed5555", "#43b581", "#f04747", "#faa61a", "#a3a3a3"])
    path = create_quote_image(quote.content, background_color=background_color)
    file = discord.File(path, filename=f'{ctx.channel_id}.png')
    os.remove(path)
    
    # Create the embed
    embed = discord.Embed(title='Guess the Quote', description=quote.content, color=0x00ff00)
    embed.add_field(name='Who said that??', value=':eyes:', inline=True)
    
    # Get original message
    guild = Guild.get_or_none(guildid=ctx.guild.id)
    jump_url = None
    if guild:
        channel = bot.get_channel(guild.quoteChannel)
        if channel:
            try:
                message = await channel.fetch_message(quote.messageid)
                if message:
                    embed.set_author(name=f"Submitted by {message.author.name}", icon_url=message.author.avatar.url)
                    jump_url = message.jump_url
            except discord.NotFound:
                logger.error(f'Message not found: {quote.messageid} - {channel.name} - {channel.id}')
    
    # Create the view
    view = discord.ui.View(timeout=120)
    
    # Add button to reveal the quote
    revealButton = discord.ui.Button(label='Reveal', style=discord.ButtonStyle.primary)
    async def button_callback(interaction):
        # set the author
        embed.set_field_at(0, name='Who said that??', value=quote.author, inline=True)
        
        # set the jump url
        if jump_url:
            embed.add_field(name='Message Link', value=f'[Jump to Message]({message.jump_url})', inline=True)
        
        # create the image with the author
        path = create_quote_image(quote.content, quote.author, background_color=background_color)
        file = discord.File(path, filename=f'{ctx.channel_id}-2.png')
        os.remove(path)
        
        embed.set_image(url=f'attachment://{ctx.channel_id}-2.png')
        embed.set_footer(text='Quote revealed by ' + interaction.user.name, icon_url=interaction.user.avatar.url)
        view.remove_item(revealButton)
        await interaction.response.edit_message(embed=embed, file=file, view=view)
    
    revealButton.callback = button_callback
    view.add_item(revealButton)
    
    # add button to delete the quote
    deleteButton = discord.ui.Button(label='Not a quote!', style=discord.ButtonStyle.danger)
    async def button_callback(interaction: discord.Interaction):
        await interaction.delete_original_response()
        await interaction.response.send_message('Deleting quote...', ephemeral=True)
        Quote.delete().where(Quote.messageid == quote.messageid).execute()
        await interaction.followup.send('Quote deleted', ephemeral=True)
    deleteButton.callback = button_callback
    view.add_item(deleteButton)
    
    embed.set_image(url=f'attachment://{ctx.channel_id}.png')
    await ctx.respond(embed=embed, file=file, view=view)
    
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