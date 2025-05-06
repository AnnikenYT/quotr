import re

# Standard Quote Formats
# "<quote>" - <author>
# <author>: <quote>
# "<quote>" <author>

regexes = [
    (r'\"(.+)\"\s(.+)', lambda match: (match.group(1), match.group(2))),      # "<quote>" <author>
    (r'(.+):\s\"?(.+)\"?', lambda match: (match.group(2), match.group(1))),   # <author>: <quote> (swapped groups)
    (r'\"(.+?)\"\s-\s(.+)', lambda match: (match.group(1), match.group(2))),  # "<quote>" - <author>
]

def addRegex(pattern, groupHandler):
    """
    Adds a new regex pattern and its corresponding group handler to the list of regexes.
    
    Args:
        pattern (str): The regex pattern to add.
        groupHandler (function): A function that takes a regex match object and returns a tuple (quote, author).
    """
    regexes.append((pattern, groupHandler))

def extractQuote(message, customRegex=None, customReverse=False):
    """
    Extracts the quote and author from a message using regex patterns.
    If multiple quotes are present, only the last author's name is extracted,
    and the preceding quotes are treated as part of the content.
    
    Args:
        message (str): The message to extract the quote from.
        customRegex (str, optional): A custom regex pattern to use for extraction.
        customReverse (bool, optional): If True, reverses the group order for the custom regex.
    
    Returns:
        tuple: A tuple containing the combined content and the last author, or None if not found.
    """
    if customRegex:
        if customReverse:
            addRegex(customRegex, lambda match: (match.group(2), match.group(1)))
        else:
            addRegex(customRegex, lambda match: (match.group(1), match.group(2)))

    last_quote = None
    last_author = None

    # Try each regex pattern
    for regex, handler in regexes:
        matches = list(re.finditer(regex, message))
        if matches:
            last_match = matches[-1]
            last_quote, last_author = handler(last_match)
            # Combine all preceding content with the last quote
            preceding_content = message[:last_match.start()].strip()
            if preceding_content:
                last_quote = f'{preceding_content}\n"{last_quote}"'
            else:
                last_quote = f'"{last_quote}"'
            break

    if last_quote and last_author:
        return last_quote, last_author

    return None