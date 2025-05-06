import discord
from db import Guild, Quote
from regexes import extractQuote
from logger import logger
import asyncio

async def process_message(message: discord.Message):
    # check if the message has a checkmark or trash reaction
    if any(reaction.emoji == '🗑️' for reaction in message.reactions):
        logger.info(f'Message excluded: {message.id}')
        return
    # add a repeat emoji and remove the checkmark reaction if it exists
    await message.add_reaction('🔁')
    try:
        await message.remove_reaction('✅', message.guild.me)
    except discord.NotFound:
        pass
    
    # extract the quote and author from the message
    quote, author = extractQuote(message.content)
    
    if quote and author:
        # check if the quote already exists in the database
        existing_quote = Quote.get_or_none(Quote.messageid == message.id)
        if not existing_quote:
            # create a new quote entry in the database
            Quote.create(guildid=message.guild.id, messageid=message.id, content=quote, author=author)
            logger.info(f'Quote added: {quote} - {author} - {message.id}')
        else:
            Quote.update(content=quote, author=author).where(Quote.messageid == message.id).execute()
            logger.info(f'Quote updated: {quote} - {author} - {message.id}')
        await message.remove_reaction('🔁', message.guild.me)
        await message.add_reaction('✅')
    else:
        logger.info(f'No quote found in message: {message.id}')
        await message.remove_reaction('🔁', message.guild.me)
        # add x emoji to the message and remove it after 5 seconds
        await message.add_reaction('❌')
        await asyncio.sleep(5)
        await message.remove_reaction('❌', message.guild.me)
        
    

async def processChannelMessages(channel: discord.TextChannel, limit = 500):
    # get the guild from the database
    processed_count = 0
    start = None
    while processed_count < limit:
        async for message in channel.history(limit=100, before=start):
            await process_message(message)
            processed_count += 1
            start = message.created_at  # update the starting point for the next batch
            logger.info(f'Processed {processed_count} messages in {channel.name} - {channel.id}')
            if processed_count >= 500:
                break
        await asyncio.sleep(0.5)  # to avoid hitting the rate limit
    

async def clearQuotes(channel: discord.TextChannel, guild: int, botuser: discord.User):
    quotes = Quote.select().where(Quote.guildid == guild, Quote.messageid != None)
    for quote in quotes:
        try:
            message = await channel.fetch_message(quote.messageid)
            if message:
                # remove the bot's reaction from the message
                await message.remove_reaction('✅', botuser)
                logger.info(f'Removed reaction from message: {message.id} - {channel.name} - {channel.id}')
        except discord.NotFound:
            logger.error(f'Message not found: {quote.messageid} - {channel.name} - {channel.id}')
        except Exception as e:
            logger.error(f'Error removing reaction from message: {e}')
    # delete all quotes from the database
    Quote.delete().where(Quote.guildid == guild).execute()
    guild, _ = Guild.get_or_create(guildid=guild)
    guild.quotesProcessedUntil = 0
    guild.save()