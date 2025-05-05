<p align="center">
    <img src="assets/icon.png" height=200> <br>
</p>

<h1 align="center">Quot.r</h1>

(Don't judge the code quality, this was written at 1am in 1.5 hours.)

## *Who said that??*

This Bot takes Quotes from your Discord Server and turns them into a game!
After setting a Quote Channel (`/setquotechannel`) and optionally a custom regex (`/setquoteregex`), the Bot will scan (can be reinitiated `/scan`) the past 500 messages of the channel and build a Database.

With `/guess`, your members will get a randow quote, and can then guess who its from!

The concept is extremely simple, but its honestly pretty funny.

**Invite Link:** Soon (maybe)

## Supported Formats

```
 "<quote>" - <author>
 <author>: <quote>   
 "<quote>" <author>
 Custom via Regex.
```

## Commands

- `*`: Requires the `Manage Server` permission


- `/setquotechannel* [channel]` :mag: : Set the channel to scan for quotes. Without arguments, it'll use the current channel.
- `/setquoteregex* <regex>` :mag: : Set a custom regex to filter messages.
- `/scan*` :mag: : Scan the set quote channel for quotes.
- `/clearquotes*` :mag: : Clear the quotes from the database.
- `/guess` :mag: : Start the guessing game.
- `/quote` :mag: : Get a random quote from the database.
- `/guildinfo` :mag: : Get information about the guild.


## Contributing

1. Clone the repo
    ```bash
    git clone https://www.github.com/annikenyt/quotr
    cd quotr
    ```
2. Install dependencies
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3. Copy the `.env.example` to `.env` and fill in your values.
4. Run the bot
    ```bash
    python3 main.py
    ```

Have Fun!

<p align="center">
    <img src="assets/banner.png"> <br>
</p>