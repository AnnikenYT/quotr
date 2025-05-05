import discord
from db import Guild, Quote
from extractQuote import extractQuote
from logger import logger
import asyncio

async def processChannelMessages(channel: discord.TextChannel):
    # get the guild from the database
    guild, _ = Guild.get_or_create(guildid=channel.guild.id)
    if guild.quotesProcessedUntil == 0:
        start = None
    else:
        start = guild.quotesProcessedUntil
    processed_count = 0
    while processed_count < 500:
        async for message in channel.history(limit=100, before=start):
            # check if the message has a checkmark or trash reaction
            if any(reaction.emoji == '✅' for reaction in message.reactions):
                logger.info(f'Message already processed: {message.id} - {channel.name} - {channel.id}')
                continue
            if any(reaction.emoji == '🗑️' for reaction in message.reactions):
                logger.info(f'Message excluded for deletion: {message.id} - {channel.name} - {channel.id}')
                continue
            quote = extractQuote(message.content)
            if quote:
                try:
                    Quote.create(messageid=message.id, guildid=channel.guild.id, author=quote[1], content=quote[0])
                    # react to the message with a checkmark
                    await message.add_reaction('✅')
                    logger.info(f'Created new quote in database: {message.id} - {channel.guild.name} - {channel.guild.id}')
                except Exception as e:
                    logger.error(f'Error creating new quote in database: {e}')
            processed_count += 1
            start = message.created_at  # update the starting point for the next batch
            guild.quotesProcessedUntil = start
            guild.save()
            logger.info(f'Processed {processed_count} messages in {channel.name} - {channel.id}')
            if processed_count >= 500:
                break
        await asyncio.sleep(0.5)  # to avoid hitting the rate limit

    # Set the quotesProcessedUntil to the snowflake of the last message processed
    guild, _ = Guild.get_or_create(guildid=channel.guild.id)
    guild.quotesProcessedUntil = start
    guild.save()
    

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